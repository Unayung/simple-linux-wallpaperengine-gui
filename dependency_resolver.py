"""Resolve wallpaper dependencies for preset-only wallpapers.

Some Steam Workshop wallpapers are "preset-only" — they contain just a
project.json with configuration and media files, but depend on another
workshop item for the actual rendering engine (typically an index.html).

This module detects such wallpapers, locates or downloads the dependency,
and creates a merged directory that linux-wallpaperengine can render.
"""

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

WALLPAPER_ENGINE_APP_ID = "431960"

# Cache dir for merged wallpapers so we don't recreate every launch
_CACHE_DIR = Path(
    os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
) / "linux-wallpaperengine-gui" / "merged"

logger = logging.getLogger(__name__)


def read_project_json(wallpaper_path: str) -> Optional[dict]:
    """Read and parse project.json from a wallpaper directory."""
    proj = os.path.join(wallpaper_path, "project.json")
    if not os.path.isfile(proj):
        return None
    try:
        with open(proj, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read project.json at %s: %s", proj, e)
        return None


def get_dependency_id(project_data: dict) -> Optional[str]:
    """Return the dependency workshop ID if this is a preset-only wallpaper."""
    if "type" in project_data and "file" in project_data:
        return None  # Already has type+file, no resolution needed
    dep = project_data.get("dependency")
    if dep and str(dep).strip():
        return str(dep).strip()
    return None


def find_workshop_item(workshop_id: str, workshop_dirs: set[str]) -> Optional[str]:
    """Find a workshop item's directory across all known workshop directories."""
    for w_dir in workshop_dirs:
        candidate = os.path.join(w_dir, workshop_id)
        if os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, "project.json")):
            return candidate
    return None


def create_merged_wallpaper(wallpaper_path: str, dependency_path: str) -> Optional[str]:
    """Create a merged directory combining dependency engine + wallpaper preset.

    The merged directory contains:
    - All files from the dependency (the rendering engine)
    - All files from the wallpaper overlaid on top (media + preset config)
    - A patched project.json with type/file from dependency + preset from wallpaper

    Returns the path to the merged directory, or None on failure.
    """
    wp_data = read_project_json(wallpaper_path)
    dep_data = read_project_json(dependency_path)
    if not wp_data or not dep_data:
        return None

    dep_type = dep_data.get("type")
    dep_file = dep_data.get("file")
    if not dep_type or not dep_file:
        logger.error("Dependency %s is also missing type/file", dependency_path)
        return None

    # Use a stable cache path based on wallpaper ID
    wp_id = os.path.basename(wallpaper_path)
    dep_id = os.path.basename(dependency_path)
    merged_dir = _CACHE_DIR / f"{wp_id}_dep_{dep_id}"

    # Recreate if source is newer than cache
    if merged_dir.exists():
        cache_mtime = merged_dir.stat().st_mtime
        wp_mtime = Path(wallpaper_path).stat().st_mtime
        dep_mtime = Path(dependency_path).stat().st_mtime
        if cache_mtime >= max(wp_mtime, dep_mtime):
            logger.info("Using cached merged wallpaper at %s", merged_dir)
            return str(merged_dir)
        shutil.rmtree(merged_dir, ignore_errors=True)

    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Step 1: Copy dependency (the engine) as the base
        shutil.copytree(dependency_path, merged_dir)

        # Step 2: Overlay wallpaper files on top (skip project.json, we'll merge it)
        for item in os.listdir(wallpaper_path):
            if item == "project.json":
                continue
            src = os.path.join(wallpaper_path, item)
            dst = merged_dir / item
            if os.path.isdir(src):
                if dst.exists():
                    # Merge subdirectories
                    for sub in os.listdir(src):
                        s = os.path.join(src, sub)
                        d = dst / sub
                        if os.path.isdir(s):
                            if d.exists():
                                shutil.rmtree(d)
                            shutil.copytree(s, d)
                        else:
                            shutil.copy2(s, d)
                else:
                    shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        # Step 3: Create merged project.json
        merged_project = dict(dep_data)
        # Inherit title, description, preview, tags from the wallpaper
        for key in ("title", "description", "preview", "tags", "contentrating", "visibility"):
            if key in wp_data:
                merged_project[key] = wp_data[key]
        # Keep the preset from the wallpaper
        if "preset" in wp_data:
            merged_project["preset"] = wp_data["preset"]
        # Ensure general.properties includes preset values for --set-property
        if "preset" in wp_data and "general" in merged_project:
            gen = merged_project["general"]
            if "properties" in gen:
                for k, v in wp_data["preset"].items():
                    if v is not None and k in gen["properties"]:
                        prop = gen["properties"][k]
                        if isinstance(prop, dict) and "value" in prop:
                            prop["value"] = v

        with open(merged_dir / "project.json", "w", encoding="utf-8") as f:
            json.dump(merged_project, f, indent=2)

        logger.info("Created merged wallpaper at %s", merged_dir)
        return str(merged_dir)

    except Exception as e:
        logger.error("Failed to create merged wallpaper: %s", e)
        if merged_dir.exists():
            shutil.rmtree(merged_dir, ignore_errors=True)
        return None


def resolve_wallpaper(wallpaper_path: str, workshop_dirs: set[str]) -> tuple[str, Optional[str]]:
    """Resolve a wallpaper path, handling dependencies if needed.

    Returns:
        (resolved_path, missing_dep_id)
        - If no dependency needed: (wallpaper_path, None)
        - If dependency resolved: (merged_path, None)
        - If dependency missing: (wallpaper_path, dependency_workshop_id)
    """
    project = read_project_json(wallpaper_path)
    if not project:
        return wallpaper_path, None

    dep_id = get_dependency_id(project)
    if not dep_id:
        return wallpaper_path, None

    dep_path = find_workshop_item(dep_id, workshop_dirs)
    if not dep_path:
        return wallpaper_path, dep_id

    merged = create_merged_wallpaper(wallpaper_path, dep_path)
    if merged:
        return merged, None

    return wallpaper_path, None
