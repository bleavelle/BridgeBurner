"""
Project management endpoints for Bridge Burner v2
"""
import os
import json
import subprocess
import shutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    get_library_path,
    PROJECT_SUBDIRS,
    IMAGE_EXTENSIONS,
    RAW_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from services.files import get_project_files, get_file_info
from services.thumbnails import get_or_create_thumbnail, get_or_create_preview

router = APIRouter()


class CullRequest(BaseModel):
    """Request body for culling/keeping files"""
    filename: str


class ProjectStats(BaseModel):
    """Project statistics"""
    name: str
    total_files: int
    culled_count: int
    raw_count: int
    jpeg_count: int
    video_count: int
    other_count: int


def get_metadata_path(project_path: str) -> str:
    """Get path to project metadata file"""
    return os.path.join(project_path, ".metadata.json")


def load_metadata(project_path: str) -> dict:
    """Load project metadata, creating default if missing"""
    metadata_path = get_metadata_path(project_path)

    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                return json.load(f)
        except Exception:
            pass

    # Create default metadata
    return {
        "notes": "",
        "created": datetime.now().isoformat(),
        "project_name": os.path.basename(project_path),
        "culled_files": [],
        "session_notes": [],
    }


def save_metadata(project_path: str, metadata: dict) -> None:
    """Save project metadata"""
    metadata_path = get_metadata_path(project_path)
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)


def is_valid_project(folder_path: str) -> bool:
    """Check if a folder is a valid project (has required subdirectories)"""
    if not os.path.isdir(folder_path):
        return False

    # Check for project subdirectories
    for subdir in PROJECT_SUBDIRS:
        subdir_path = os.path.join(folder_path, subdir)
        if os.path.exists(subdir_path):
            return True

    return False


@router.get("")
async def list_projects():
    """List all projects in the library"""
    library_path = get_library_path()

    if not os.path.exists(library_path):
        return {"projects": [], "library_path": library_path}

    projects = []
    for name in os.listdir(library_path):
        project_path = os.path.join(library_path, name)
        if is_valid_project(project_path):
            metadata = load_metadata(project_path)
            files = get_project_files(project_path)

            projects.append({
                "name": name,
                "path": project_path,
                "total_files": len(files),
                "culled_count": len(metadata.get("culled_files", [])),
                "created": metadata.get("created"),
                "notes": metadata.get("notes", ""),
            })

    # Sort by name
    projects.sort(key=lambda p: p["name"].lower())
    return {"projects": projects, "library_path": library_path}


@router.get("/{name}")
async def get_project(name: str):
    """Get project details and file list"""
    library_path = get_library_path()
    project_path = os.path.join(library_path, name)

    if not is_valid_project(project_path):
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    metadata = load_metadata(project_path)
    files = get_project_files(project_path)
    culled_files = set(metadata.get("culled_files", []))

    file_list = []
    for filepath in files:
        info = get_file_info(filepath)
        info["culled"] = info["filename"] in culled_files
        file_list.append(info)

    # Sort by filename
    file_list.sort(key=lambda f: f["filename"].lower())

    return {
        "name": name,
        "path": project_path,
        "files": file_list,
        "metadata": metadata,
        "stats": {
            "total": len(files),
            "culled": len(culled_files),
            "kept": len(files) - len([f for f in file_list if f["culled"]]),
        },
    }


@router.get("/{name}/files/{filename:path}")
async def get_file(name: str, filename: str):
    """Serve an image/video file (converts RAW to JPEG for browser display)"""
    library_path = get_library_path()
    project_path = os.path.join(library_path, name)

    if not is_valid_project(project_path):
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    # Search for file in all subdirectories
    for subdir in PROJECT_SUBDIRS:
        filepath = os.path.join(project_path, subdir, filename)
        if os.path.exists(filepath):
            # Check if it's a RAW file - need to convert for browser
            ext = os.path.splitext(filename)[1].lower()
            if ext in RAW_EXTENSIONS:
                preview_path = get_or_create_preview(filepath, project_path)
                if preview_path and os.path.exists(preview_path):
                    return FileResponse(preview_path, media_type="image/jpeg")
            # Regular file (JPEG, video, etc) - serve directly
            return FileResponse(filepath)

    raise HTTPException(status_code=404, detail=f"File '{filename}' not found")


@router.get("/{name}/thumbnail/{filename:path}")
async def get_thumbnail(name: str, filename: str):
    """Serve a thumbnail for an image"""
    library_path = get_library_path()
    project_path = os.path.join(library_path, name)

    if not is_valid_project(project_path):
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    # Search for file in all subdirectories
    for subdir in PROJECT_SUBDIRS:
        filepath = os.path.join(project_path, subdir, filename)
        if os.path.exists(filepath):
            thumbnail_path = get_or_create_thumbnail(filepath, project_path)
            if thumbnail_path and os.path.exists(thumbnail_path):
                return FileResponse(thumbnail_path)
            # Fall back to original file
            return FileResponse(filepath)

    raise HTTPException(status_code=404, detail=f"File '{filename}' not found")


@router.post("/{name}/cull")
async def cull_file(name: str, request: CullRequest):
    """Mark a file as culled"""
    library_path = get_library_path()
    project_path = os.path.join(library_path, name)

    if not is_valid_project(project_path):
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    metadata = load_metadata(project_path)
    culled_files = set(metadata.get("culled_files", []))
    culled_files.add(request.filename)
    metadata["culled_files"] = list(culled_files)
    save_metadata(project_path, metadata)

    return {"status": "culled", "filename": request.filename}


@router.post("/{name}/keep")
async def keep_file(name: str, request: CullRequest):
    """Unmark a file as culled (keep it)"""
    library_path = get_library_path()
    project_path = os.path.join(library_path, name)

    if not is_valid_project(project_path):
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    metadata = load_metadata(project_path)
    culled_files = set(metadata.get("culled_files", []))
    culled_files.discard(request.filename)
    metadata["culled_files"] = list(culled_files)
    save_metadata(project_path, metadata)

    return {"status": "kept", "filename": request.filename}


@router.delete("/{name}/culled")
async def delete_culled(name: str):
    """Delete all culled files from a project"""
    library_path = get_library_path()
    project_path = os.path.join(library_path, name)

    if not is_valid_project(project_path):
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    metadata = load_metadata(project_path)
    culled_files = metadata.get("culled_files", [])

    deleted = []
    errors = []

    for filename in culled_files:
        # Search in all subdirectories
        found = False
        for subdir in PROJECT_SUBDIRS:
            filepath = os.path.join(project_path, subdir, filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    deleted.append(filename)
                    found = True
                    break
                except Exception as e:
                    errors.append({"filename": filename, "error": str(e)})
                    found = True
                    break

        if not found:
            # File already gone, just remove from list
            deleted.append(filename)

    # Clear culled files list
    metadata["culled_files"] = []
    save_metadata(project_path, metadata)

    return {
        "deleted": deleted,
        "errors": errors,
        "total_deleted": len(deleted),
    }


class OpenInAppRequest(BaseModel):
    """Request to open a file in an external app"""
    filepath: str


@router.post("/{name}/open-in-gimp")
async def open_in_gimp(name: str, request: OpenInAppRequest):
    """Open an image file in GIMP"""
    library_path = get_library_path()
    project_path = os.path.join(library_path, name)

    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail=f"Project not found: {name}")

    # Build full path and validate it's within project
    filepath = request.filepath
    if not os.path.isabs(filepath):
        filepath = os.path.join(project_path, filepath)

    filepath = os.path.normpath(filepath)

    # Security check - must be within project
    if not filepath.startswith(os.path.normpath(project_path)):
        raise HTTPException(status_code=403, detail="Access denied - file outside project")

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")

    try:
        # GIMP 3 from Windows Store - use the app execution alias
        gimp_exe = os.path.expanduser(r"~\AppData\Local\Microsoft\WindowsApps\gimp-3.exe")
        subprocess.Popen([gimp_exe, filepath])
        return {"success": True, "message": f"Opening in GIMP: {os.path.basename(filepath)}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open GIMP: {str(e)}")
