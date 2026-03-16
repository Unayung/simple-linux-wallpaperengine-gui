"""SteamCMD wrapper for authentication and workshop item downloads."""

import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


WALLPAPER_ENGINE_APP_ID = "431960"

# Shared thread pool for background steamcmd operations
_pool = ThreadPoolExecutor(max_workers=2)


class DownloadStatus(Enum):
    DOWNLOADING = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class DownloadState:
    status: DownloadStatus
    message: str = ""


def _run_steamcmd_blocking(cmd_path: str, arguments: list[str], timeout: int = 30) -> tuple[str, int]:
    """Run steamcmd synchronously — call from background thread only."""
    try:
        result = subprocess.run(
            [cmd_path] + arguments,
            capture_output=True, text=True, timeout=timeout,
        )
        return (result.stdout + result.stderr, result.returncode)
    except subprocess.TimeoutExpired:
        return (f"steamcmd timed out after {timeout}s", -1)
    except Exception as e:
        return (f"Failed to run steamcmd: {e}", -1)


def _parse_progress(line: str) -> Optional[str]:
    """Parse a steamcmd output line into a human-readable status string."""
    s = line.strip()
    if not s:
        return None
    if "Logging in" in s or "Logged in" in s:
        return "Authenticating..."
    if "Downloading item" in s or "workshop_download_item" in s:
        return "Requesting download..."
    if "ownloading" in s:
        m = re.search(r"progress:\s*([\d.]+)", s)
        if m:
            pct = min(float(m.group(1)), 100)
            return f"Downloading... {pct:.0f}%"
        return "Downloading..."
    if "Validating" in s or "validating" in s:
        return "Validating..."
    if "Success" in s:
        return "Download complete, importing..."
    if "Update state" in s:
        if "0x5" in s:
            return "Validating..."
        if "0x61" in s:
            return "Downloading..."
        if "0x101" in s:
            return "Committing..."
    return None


class SteamCmdService(QObject):
    """Manages steamcmd detection, login, and workshop downloads.

    All background work uses ThreadPoolExecutor + QTimer polling to avoid
    cross-thread signal crashes on Python 3.14 + PyQt6.
    """

    login_state_changed = pyqtSignal()
    download_updated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steamcmd_path: Optional[str] = None
        self.is_logged_in = False
        self.is_logging_in = False
        self.username = ""
        self.login_error: Optional[str] = None
        self.download_progress: dict[str, DownloadState] = {}
        self._pending_futures: list = []
        self._detect_steamcmd()

    @property
    def is_installed(self) -> bool:
        return self.steamcmd_path is not None

    # -- Detection --

    def _detect_steamcmd(self):
        search_paths = [
            "/usr/bin/steamcmd",
            "/usr/local/bin/steamcmd",
            os.path.expanduser("~/.local/bin/steamcmd"),
            os.path.expanduser("~/.steam/steamcmd/steamcmd.sh"),
        ]
        for p in search_paths:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                self.steamcmd_path = p
                return
        try:
            result = subprocess.run(
                ["which", "steamcmd"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                if path and os.path.isfile(path):
                    self.steamcmd_path = path
        except Exception:
            pass

    def set_custom_path(self, path: str) -> bool:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            self.steamcmd_path = path
            return True
        return False

    def redetect(self):
        self.steamcmd_path = None
        self._detect_steamcmd()

    # -- Async helper --

    def _run_async(self, func, callback):
        """Submit func to thread pool and poll for result on main thread."""
        future = _pool.submit(func)
        timer = QTimer(self)
        timer.setInterval(50)
        ref = [future, timer]
        self._pending_futures.append(ref)

        def _check():
            if future.done():
                timer.stop()
                self._pending_futures.remove(ref)
                try:
                    result = future.result()
                except Exception as e:
                    result = e
                callback(result)

        timer.timeout.connect(_check)
        timer.start()

    # -- Login --

    def login(self, username: str, password: str, guard_code: str = ""):
        if not self.steamcmd_path:
            return
        self.is_logging_in = True
        self.login_error = None
        self.username = username
        self.login_state_changed.emit()

        args = ["+login", username, password]
        if guard_code:
            args = ["+login", username, password, guard_code]
        args += ["+quit"]

        def _do():
            return _run_steamcmd_blocking(self.steamcmd_path, args, timeout=60)

        self._run_async(_do, lambda r: self._handle_login_result(r, username, cached=False))

    def login_cached(self, username: str):
        if not self.steamcmd_path:
            return
        self.is_logging_in = True
        self.login_error = None
        self.username = username
        self.login_state_changed.emit()

        def _do():
            return _run_steamcmd_blocking(self.steamcmd_path, ["+login", username, "+quit"], timeout=30)

        self._run_async(_do, lambda r: self._handle_login_result(r, username, cached=True))

    def _handle_login_result(self, result, username: str, cached: bool = False):
        if isinstance(result, Exception):
            self.is_logging_in = False
            self.login_error = str(result)
            self.login_state_changed.emit()
            return

        output, exit_code = result
        self.is_logging_in = False
        if "Logged in OK" in output or ("OK" in output and exit_code == 0):
            self.is_logged_in = True
            self.login_error = None
        elif "Steam Guard" in output or "Two-factor" in output:
            self.login_error = "Steam Guard code required"
        elif "Invalid Password" in output or "FAILED" in output:
            self.login_error = "Invalid username or password"
        elif cached:
            self.login_error = "Cached session expired. Please log in with password."
        else:
            self.login_error = "Login failed. Check credentials and try again."
        self.login_state_changed.emit()

    # -- Download --

    def download_workshop_item(self, workshop_id: str, dest_dir: str):
        """Download a workshop item and copy it to dest_dir/<workshop_id>."""
        if not self.steamcmd_path or not self.is_logged_in:
            return

        self.download_progress[workshop_id] = DownloadState(DownloadStatus.DOWNLOADING, "Starting steamcmd...")
        self.download_updated.emit(workshop_id)

        def _do():
            return self._download_blocking(workshop_id)

        self._run_async(_do, lambda r: self._handle_download_result(r, workshop_id, dest_dir))

    def _download_blocking(self, workshop_id: str) -> tuple[str, int]:
        """Run the download in a background thread. Returns (full_output, exit_code)."""
        try:
            process = subprocess.Popen(
                [self.steamcmd_path,
                 "+login", self.username,
                 "+workshop_download_item", WALLPAPER_ENGINE_APP_ID, workshop_id, "validate",
                 "+quit"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            full_output = ""
            for line in iter(process.stdout.readline, ""):
                full_output += line
                # Note: progress updates can't use signals from here.
                # We update progress dict; the UI can poll if needed.
                status = _parse_progress(line)
                if status:
                    self.download_progress[workshop_id] = DownloadState(DownloadStatus.DOWNLOADING, status)

            process.wait(timeout=600)
            return (full_output, process.returncode)
        except Exception as e:
            return (str(e), -1)

    def _handle_download_result(self, result, workshop_id: str, dest_dir: str):
        if isinstance(result, Exception):
            self.download_progress[workshop_id] = DownloadState(DownloadStatus.FAILED, str(result))
            self.download_updated.emit(workshop_id)
            return

        full_output, exit_code = result

        source = self._find_downloaded_content(workshop_id)
        if source and os.path.isdir(source):
            target = os.path.join(dest_dir, workshop_id)
            if not os.path.exists(target):
                try:
                    self.download_progress[workshop_id] = DownloadState(DownloadStatus.DOWNLOADING, "Copying to library...")
                    self.download_updated.emit(workshop_id)
                    shutil.copytree(source, target)
                except Exception as e:
                    self.download_progress[workshop_id] = DownloadState(DownloadStatus.FAILED, f"Copy failed: {e}")
                    self.download_updated.emit(workshop_id)
                    return
            self.download_progress[workshop_id] = DownloadState(DownloadStatus.COMPLETED)
            self.download_updated.emit(workshop_id)
        elif "ERROR" in full_output or "FAILED" in full_output:
            err = next((l for l in full_output.splitlines() if "ERROR" in l or "FAILED" in l), "Unknown error")
            self.download_progress[workshop_id] = DownloadState(DownloadStatus.FAILED, err)
            self.download_updated.emit(workshop_id)
        elif exit_code != 0:
            self.download_progress[workshop_id] = DownloadState(DownloadStatus.FAILED, f"Exit code {exit_code}")
            self.download_updated.emit(workshop_id)
        else:
            self.download_progress[workshop_id] = DownloadState(DownloadStatus.FAILED, "Files not found at expected path")
            self.download_updated.emit(workshop_id)

    def _find_downloaded_content(self, workshop_id: str) -> Optional[str]:
        if not self.steamcmd_path:
            return None
        cmd_dir = os.path.dirname(self.steamcmd_path)
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(cmd_dir, "steamapps", "workshop", "content", WALLPAPER_ENGINE_APP_ID, workshop_id),
            os.path.join(home, ".local", "share", "Steam", "steamapps", "workshop", "content", WALLPAPER_ENGINE_APP_ID, workshop_id),
            os.path.join(home, ".steam", "steam", "steamapps", "workshop", "content", WALLPAPER_ENGINE_APP_ID, workshop_id),
        ]
        for c in candidates:
            if os.path.isdir(c):
                return c
        return None
