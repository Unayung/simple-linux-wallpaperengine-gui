"""SteamCMD wrapper for authentication and workshop item downloads."""

import os
import re
import shutil
import subprocess
import threading
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Callable

from PyQt6.QtCore import QObject, pyqtSignal


WALLPAPER_ENGINE_APP_ID = "431960"


class DownloadStatus(Enum):
    DOWNLOADING = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class DownloadState:
    status: DownloadStatus
    message: str = ""


class SteamCmdService(QObject):
    """Manages steamcmd detection, login, and workshop downloads."""

    login_state_changed = pyqtSignal()       # emitted on login success/failure
    download_updated = pyqtSignal(str)        # emitted with workshop_id when progress changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steamcmd_path: Optional[str] = None
        self.is_logged_in = False
        self.is_logging_in = False
        self.username = ""
        self.login_error: Optional[str] = None
        self.download_progress: dict[str, DownloadState] = {}
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

        # Fallback: which
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

    # -- Running steamcmd --

    def _run_steamcmd(self, arguments: list[str], timeout: int = 30) -> tuple[str, int]:
        if not self.steamcmd_path:
            return ("steamcmd not found", -1)
        try:
            result = subprocess.run(
                [self.steamcmd_path] + arguments,
                capture_output=True, text=True, timeout=timeout,
            )
            output = result.stdout + result.stderr
            return (output, result.returncode)
        except subprocess.TimeoutExpired:
            return (f"steamcmd timed out after {timeout}s", -1)
        except Exception as e:
            return (f"Failed to run steamcmd: {e}", -1)

    # -- Login --

    def login(self, username: str, password: str, guard_code: str = ""):
        if not self.steamcmd_path:
            return
        self.is_logging_in = True
        self.login_error = None
        self.username = username
        self.login_state_changed.emit()

        def _do_login():
            args = ["+login", username, password]
            if guard_code:
                args = ["+login", username, password, guard_code]
            args += ["+quit"]
            output, exit_code = self._run_steamcmd(args, timeout=60)
            self._handle_login_result(output, exit_code, username)

        threading.Thread(target=_do_login, daemon=True).start()

    def login_cached(self, username: str):
        if not self.steamcmd_path:
            return
        self.is_logging_in = True
        self.login_error = None
        self.username = username
        self.login_state_changed.emit()

        def _do_login():
            output, exit_code = self._run_steamcmd(["+login", username, "+quit"], timeout=30)
            self._handle_login_result(output, exit_code, username, cached=True)

        threading.Thread(target=_do_login, daemon=True).start()

    def _handle_login_result(self, output: str, exit_code: int, username: str, cached: bool = False):
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

        def _do_download():
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
                    status = self._parse_progress(line)
                    if status:
                        self.download_progress[workshop_id] = DownloadState(DownloadStatus.DOWNLOADING, status)
                        self.download_updated.emit(workshop_id)

                process.wait(timeout=600)
                exit_code = process.returncode
            except Exception as e:
                self.download_progress[workshop_id] = DownloadState(DownloadStatus.FAILED, str(e))
                self.download_updated.emit(workshop_id)
                return

            # Find and copy downloaded content
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

        threading.Thread(target=_do_download, daemon=True).start()

    def _parse_progress(self, line: str) -> Optional[str]:
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
