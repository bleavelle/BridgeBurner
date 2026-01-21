"""
Configuration management for Bridge Burner v2
Compatible with v1 .bridge_burner_config.json format
"""
import os
import json

# App directory is the backend folder's parent
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(BACKEND_DIR)

# Config file location - check both v2 location and v1 location
CONFIG_FILE_V2 = os.path.join(APP_DIR, ".bridge_burner_config.json")
CONFIG_FILE_V1 = os.path.join(os.path.expanduser("~"), "Documents", "photo_organizer", ".bridge_burner_config.json")

# Default projects directory
DEFAULT_LIBRARY_PATH = os.path.join(APP_DIR, "projects")

# Project subdirectories
PROJECT_SUBDIRS = ["RAW", "JPEG", "Video", "Other"]

# Supported file extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"}
RAW_EXTENSIONS = {".arw", ".cr2", ".cr3", ".nef", ".orf", ".raf", ".rw2", ".dng", ".raw"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".mts", ".m2ts"}

# Thumbnail settings
THUMBNAIL_SIZE = (300, 300)
THUMBNAIL_QUALITY = 85


def get_config() -> dict:
    """
    Load app configuration from config file.
    Checks v2 location first, then falls back to v1 location for compatibility.
    """
    # Try v2 location first
    if os.path.exists(CONFIG_FILE_V2):
        try:
            with open(CONFIG_FILE_V2, "r") as f:
                return json.load(f)
        except Exception:
            pass

    # Fall back to v1 location
    if os.path.exists(CONFIG_FILE_V1):
        try:
            with open(CONFIG_FILE_V1, "r") as f:
                return json.load(f)
        except Exception:
            pass

    # Return defaults
    return {"library_path": DEFAULT_LIBRARY_PATH}


def save_config(config: dict) -> None:
    """Save app configuration to config file (v2 location)"""
    with open(CONFIG_FILE_V2, "w") as f:
        json.dump(config, f, indent=2)


def get_library_path() -> str:
    """Get the configured library path"""
    config = get_config()
    return config.get("library_path", DEFAULT_LIBRARY_PATH)


def set_library_path(path: str) -> None:
    """Update the library path in config"""
    config = get_config()
    config["library_path"] = path
    save_config(config)
