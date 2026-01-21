"""
File handling utilities for Bridge Burner v2
"""
import os
from typing import List, Dict, Any

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    PROJECT_SUBDIRS,
    IMAGE_EXTENSIONS,
    RAW_EXTENSIONS,
    VIDEO_EXTENSIONS,
)


def get_file_type(filename: str) -> str:
    """Determine file type based on extension"""
    ext = os.path.splitext(filename)[1].lower()

    if ext in IMAGE_EXTENSIONS:
        return "image"
    elif ext in RAW_EXTENSIONS:
        return "raw"
    elif ext in VIDEO_EXTENSIONS:
        return "video"
    else:
        return "other"


def get_file_info(filepath: str) -> Dict[str, Any]:
    """Get information about a file"""
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1].lower()
    file_type = get_file_type(filename)

    try:
        stat = os.stat(filepath)
        size = stat.st_size
        modified = stat.st_mtime
    except Exception:
        size = 0
        modified = 0

    # Determine which subdirectory it's in
    parent_dir = os.path.basename(os.path.dirname(filepath))
    subdir = parent_dir if parent_dir in PROJECT_SUBDIRS else "Other"

    return {
        "filename": filename,
        "filepath": filepath,
        "extension": ext,
        "type": file_type,
        "subdir": subdir,
        "size": size,
        "modified": modified,
        "can_thumbnail": file_type in ("image", "raw"),
    }


def get_project_files(project_path: str) -> List[str]:
    """
    Get all media files in a project.
    Returns list of full file paths.
    """
    files = []
    all_extensions = IMAGE_EXTENSIONS | RAW_EXTENSIONS | VIDEO_EXTENSIONS

    for subdir in PROJECT_SUBDIRS:
        subdir_path = os.path.join(project_path, subdir)
        if not os.path.exists(subdir_path):
            continue

        for filename in os.listdir(subdir_path):
            # Skip hidden files and metadata
            if filename.startswith("."):
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext in all_extensions:
                files.append(os.path.join(subdir_path, filename))

    return files


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
