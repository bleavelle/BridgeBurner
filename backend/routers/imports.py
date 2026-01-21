"""
Import and conversion endpoints for Bridge Burner v2
Handles scanning folders, organizing files, and video conversion
"""
import os
import json
import shutil
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks
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
from services.conversion import (
    find_ffmpeg,
    get_ffmpeg_version,
    get_presets_list,
    convert_video,
    is_gopro_file,
    ConversionPreset,
    PRESETS,
)

router = APIRouter()

# Track active conversion jobs
active_jobs = {}

# Preview cache directory
import tempfile
PREVIEW_CACHE_DIR = os.path.join(tempfile.gettempdir(), "bridgeburner_preview_cache")


def clear_preview_cache():
    """Clear the preview image cache directory"""
    if os.path.exists(PREVIEW_CACHE_DIR):
        try:
            shutil.rmtree(PREVIEW_CACHE_DIR)
            print(f"[Cleanup] Cleared preview cache: {PREVIEW_CACHE_DIR}")
        except Exception as e:
            print(f"[Cleanup] Failed to clear preview cache: {e}")


class ScanRequest(BaseModel):
    """Request to scan a folder"""
    path: str


class ImportRequest(BaseModel):
    """Request to import files into a project"""
    source_path: str
    project_name: str
    organize: bool = True  # Organize into RAW/JPEG/Video/Other subdirs
    convert_videos: bool = False
    conversion_preset: str = "dnxhd_1080p"
    delete_originals: bool = False


class ConvertRequest(BaseModel):
    """Request to convert a single video"""
    input_path: str
    output_path: str
    preset: str = "dnxhd_1080p"


@router.get("/ffmpeg-status")
async def ffmpeg_status():
    """Check if ffmpeg is available and get version"""
    ffmpeg_path = find_ffmpeg()
    version = get_ffmpeg_version() if ffmpeg_path else None

    return {
        "available": ffmpeg_path is not None,
        "path": ffmpeg_path,
        "version": version,
    }


@router.get("/presets")
async def list_presets():
    """Get available conversion presets"""
    return {"presets": get_presets_list()}


@router.post("/browse-folder")
async def browse_folder():
    """Open native folder picker dialog and return selected path"""
    import subprocess
    import platform

    try:
        system = platform.system()

        if system == "Windows":
            # PowerShell folder picker - uses STA thread for proper COM dialog handling
            ps_script = '''
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$folder = New-Object System.Windows.Forms.FolderBrowserDialog
$folder.Description = "Select Folder"
$folder.ShowNewFolderButton = $true
$folder.RootFolder = [System.Environment+SpecialFolder]::MyComputer
$result = $folder.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $folder.SelectedPath
}
$folder.Dispose()
'''
            result = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-WindowStyle", "Hidden", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            path = result.stdout.strip()

        elif system == "Darwin":  # macOS
            # AppleScript for native folder picker
            result = subprocess.run(
                ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select Source Folder")'],
                capture_output=True,
                text=True,
                timeout=120
            )
            path = result.stdout.strip()

        else:  # Linux
            # Try zenity first (GNOME), then kdialog (KDE)
            path = None
            for cmd in [
                ["zenity", "--file-selection", "--directory", "--title=Select Source Folder"],
                ["kdialog", "--getexistingdirectory", ".", "--title", "Select Source Folder"],
            ]:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    if result.returncode == 0:
                        path = result.stdout.strip()
                        break
                except FileNotFoundError:
                    continue

        if path:
            return {"path": path, "cancelled": False}
        else:
            return {"path": None, "cancelled": True}

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Folder picker timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder picker: {str(e)}")


@router.post("/scan")
async def scan_folder(request: ScanRequest):
    """Scan a folder and return file information"""
    path = request.path

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")

    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {path}")

    files = {
        "raw": [],
        "jpeg": [],
        "video": [],
        "gopro": [],
        "other": [],
    }

    total_size = 0

    for root, dirs, filenames in os.walk(path):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in filenames:
            if filename.startswith("."):
                continue

            filepath = os.path.join(root, filename)
            ext = os.path.splitext(filename)[1].lower()

            try:
                size = os.path.getsize(filepath)
                total_size += size
            except OSError:
                size = 0

            file_info = {
                "filename": filename,
                "path": filepath,
                "size": size,
                "relative_path": os.path.relpath(filepath, path),
            }

            if ext in RAW_EXTENSIONS:
                files["raw"].append(file_info)
            elif ext in IMAGE_EXTENSIONS:
                files["jpeg"].append(file_info)
            elif ext in VIDEO_EXTENSIONS:
                # Check if it's a GoPro file
                if is_gopro_file(filepath):
                    file_info["is_gopro"] = True
                    files["gopro"].append(file_info)
                else:
                    files["video"].append(file_info)
            else:
                files["other"].append(file_info)

    return {
        "path": path,
        "files": files,
        "counts": {
            "raw": len(files["raw"]),
            "jpeg": len(files["jpeg"]),
            "video": len(files["video"]),
            "gopro": len(files["gopro"]),
            "other": len(files["other"]),
            "total": sum(len(f) for f in files.values()),
        },
        "total_size": total_size,
    }


@router.post("/date-previews")
async def get_date_previews(request: ScanRequest):
    """Get preview images grouped by date (3 per date) for quick review"""
    path = request.path

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")

    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {path}")

    from collections import defaultdict
    import random

    # Group files by date
    files_by_date = defaultdict(list)

    for root, dirs, filenames in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in filenames:
            if filename.startswith("."):
                continue

            filepath = os.path.join(root, filename)
            ext = os.path.splitext(filename)[1].lower()

            # Only include images (JPEG and RAW)
            if ext not in IMAGE_EXTENSIONS and ext not in RAW_EXTENSIONS:
                continue

            try:
                # Get file modification time as fallback
                mtime = os.path.getmtime(filepath)
                from datetime import datetime
                date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")

                # Try to get EXIF date if available (for JPEGs)
                if ext in IMAGE_EXTENSIONS:
                    try:
                        from PIL import Image
                        from PIL.ExifTags import TAGS
                        with Image.open(filepath) as img:
                            exif = img._getexif()
                            if exif:
                                for tag_id, value in exif.items():
                                    tag = TAGS.get(tag_id, tag_id)
                                    if tag == "DateTimeOriginal":
                                        # Format: "2024:01:15 14:30:00"
                                        date_str = value.split(" ")[0].replace(":", "-")
                                        break
                    except Exception:
                        pass  # Fall back to mtime

                files_by_date[date_str].append({
                    "filename": filename,
                    "filepath": filepath,
                    "ext": ext,
                    "is_raw": ext in RAW_EXTENSIONS,
                })
            except OSError:
                continue

    # Build preview data: 3 random samples per date
    previews = []
    for date_str in sorted(files_by_date.keys(), reverse=True):
        files = files_by_date[date_str]
        # Prefer JPEGs for previews (faster to load), but include RAW if no JPEGs
        jpegs = [f for f in files if not f["is_raw"]]
        raws = [f for f in files if f["is_raw"]]

        # Pick up to 3 samples, preferring JPEGs
        samples = []
        if jpegs:
            samples = random.sample(jpegs, min(3, len(jpegs)))
        if len(samples) < 3 and raws:
            samples += random.sample(raws, min(3 - len(samples), len(raws)))

        previews.append({
            "date": date_str,
            "total_count": len(files),
            "jpeg_count": len(jpegs),
            "raw_count": len(raws),
            "samples": samples,
        })

    return {
        "path": path,
        "dates": previews,
        "total_dates": len(previews),
        "total_files": sum(p["total_count"] for p in previews),
    }


@router.delete("/preview-cache")
async def delete_preview_cache():
    """Clear the preview image cache"""
    clear_preview_cache()
    return {"success": True, "message": "Preview cache cleared"}


@router.get("/preview-image")
async def get_preview_image(filepath: str):
    """Serve a preview image (generates thumbnail for RAW files)"""
    from fastapi.responses import FileResponse
    import hashlib

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    ext = os.path.splitext(filepath)[1].lower()

    # For RAW files, generate a cached preview thumbnail
    if ext in RAW_EXTENSIONS:
        try:
            import rawpy
            from PIL import Image

            # Use the global cache directory
            os.makedirs(PREVIEW_CACHE_DIR, exist_ok=True)

            # Generate cache filename based on filepath + mtime
            mtime = os.path.getmtime(filepath)
            hash_input = f"{filepath}:{mtime}"
            file_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]
            cache_path = os.path.join(PREVIEW_CACHE_DIR, f"{file_hash}.jpg")

            # Return cached version if exists
            if os.path.exists(cache_path):
                return FileResponse(cache_path, media_type="image/jpeg")

            # Generate preview from RAW
            with rawpy.imread(filepath) as raw:
                # Try embedded thumbnail first (fast)
                try:
                    thumb = raw.extract_thumb()
                    if thumb.format == rawpy.ThumbFormat.JPEG:
                        with open(cache_path, "wb") as f:
                            f.write(thumb.data)
                        # Resize if too large
                        with Image.open(cache_path) as img:
                            if img.size[0] > 300 or img.size[1] > 300:
                                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                                img.save(cache_path, "JPEG", quality=80)
                        return FileResponse(cache_path, media_type="image/jpeg")
                    elif thumb.format == rawpy.ThumbFormat.BITMAP:
                        img = Image.fromarray(thumb.data)
                        img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                        img.save(cache_path, "JPEG", quality=80)
                        return FileResponse(cache_path, media_type="image/jpeg")
                except Exception:
                    pass

                # Fall back to full RAW processing (slower)
                rgb = raw.postprocess(use_camera_wb=True, half_size=True)
                img = Image.fromarray(rgb)
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                img.save(cache_path, "JPEG", quality=80)
                return FileResponse(cache_path, media_type="image/jpeg")

        except ImportError:
            raise HTTPException(status_code=404, detail="RAW support not available (rawpy not installed)")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process RAW: {str(e)}")

    # For JPEGs, serve directly (browser will handle resizing)
    return FileResponse(filepath, media_type="image/jpeg")


@router.post("/import")
async def import_files(request: ImportRequest, background_tasks: BackgroundTasks):
    """Import files from source folder into a project"""
    source_path = request.source_path
    project_name = request.project_name
    library_path = get_library_path()

    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail=f"Source path not found: {source_path}")

    # Create project directory
    project_path = os.path.join(library_path, project_name)

    # Create subdirectories
    for subdir in PROJECT_SUBDIRS:
        os.makedirs(os.path.join(project_path, subdir), exist_ok=True)

    # Create metadata file
    metadata_path = os.path.join(project_path, ".metadata.json")
    if not os.path.exists(metadata_path):
        metadata = {
            "notes": "",
            "created": datetime.now().isoformat(),
            "project_name": project_name,
            "culled_files": [],
            "session_notes": [],
            "import_source": source_path,
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    # Scan and organize files
    imported = {"raw": 0, "jpeg": 0, "video": 0, "other": 0}
    errors = []

    for root, dirs, filenames in os.walk(source_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in filenames:
            if filename.startswith("."):
                continue

            filepath = os.path.join(root, filename)
            ext = os.path.splitext(filename)[1].lower()

            # Determine destination subdirectory
            if ext in RAW_EXTENSIONS:
                dest_subdir = "RAW"
                imported["raw"] += 1
            elif ext in IMAGE_EXTENSIONS:
                dest_subdir = "JPEG"
                imported["jpeg"] += 1
            elif ext in VIDEO_EXTENSIONS:
                dest_subdir = "Video"
                imported["video"] += 1
            else:
                dest_subdir = "Other"
                imported["other"] += 1

            dest_path = os.path.join(project_path, dest_subdir, filename)

            # Handle duplicate filenames
            counter = 1
            base_name = os.path.splitext(filename)[0]
            while os.path.exists(dest_path):
                new_filename = f"{base_name}_{counter}{ext}"
                dest_path = os.path.join(project_path, dest_subdir, new_filename)
                counter += 1

            try:
                if request.delete_originals:
                    shutil.move(filepath, dest_path)
                else:
                    shutil.copy2(filepath, dest_path)
            except Exception as e:
                errors.append({"file": filename, "error": str(e)})

    # If conversion requested, start background job
    job_id = None
    if request.convert_videos:
        job_id = f"convert_{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "current_file": None,
            "completed": 0,
            "total": imported["video"],
            "errors": [],
        }

        background_tasks.add_task(
            run_batch_conversion,
            job_id,
            project_path,
            request.conversion_preset,
        )

    return {
        "success": True,
        "project_path": project_path,
        "imported": imported,
        "errors": errors,
        "conversion_job_id": job_id,
    }


def run_batch_conversion(job_id: str, project_path: str, preset_name: str):
    """Background task to convert all videos in a project"""
    job = active_jobs[job_id]
    job["status"] = "running"

    video_dir = os.path.join(project_path, "Video")
    if not os.path.exists(video_dir):
        job["status"] = "completed"
        return

    # Get preset
    try:
        preset = ConversionPreset(preset_name)
    except ValueError:
        preset = ConversionPreset.DNXHD_1080P

    settings = PRESETS[preset]

    # Find all video files
    video_files = []
    for filename in os.listdir(video_dir):
        ext = os.path.splitext(filename)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            video_files.append(filename)

    job["total"] = len(video_files)

    for i, filename in enumerate(video_files):
        input_path = os.path.join(video_dir, filename)
        base_name = os.path.splitext(filename)[0]
        output_path = os.path.join(video_dir, base_name + settings.extension)

        # Skip if already converted
        if os.path.exists(output_path) and output_path != input_path:
            job["completed"] += 1
            continue

        job["current_file"] = filename

        def update_progress(progress, message):
            job["progress"] = progress
            job["current_message"] = message

        result = convert_video(input_path, output_path, preset, update_progress)

        if result["success"]:
            job["completed"] += 1
            # Optionally remove original after successful conversion
            # if input_path != output_path:
            #     os.remove(input_path)
        else:
            job["errors"].append({"file": filename, "error": result.get("error", "Unknown error")})

        job["progress"] = ((i + 1) / len(video_files)) * 100

    job["status"] = "completed"
    job["current_file"] = None


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a conversion job"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    job = active_jobs[job_id]
    print(f"[API] Job {job_id}: progress={job.get('progress', 0):.1f}%, status={job.get('status')}")
    return job


@router.get("/jobs")
async def list_jobs():
    """List all conversion jobs"""
    return {"jobs": active_jobs}


@router.post("/convert")
async def convert_single(request: ConvertRequest, background_tasks: BackgroundTasks):
    """Convert a single video file"""
    if not os.path.exists(request.input_path):
        raise HTTPException(status_code=404, detail=f"Input file not found: {request.input_path}")

    try:
        preset = ConversionPreset(request.preset)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid preset: {request.preset}")

    job_id = f"convert_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    active_jobs[job_id] = {
        "status": "running",
        "progress": 0,
        "input": request.input_path,
        "output": request.output_path,
        "preset": request.preset,
    }

    def run_conversion():
        def update_progress(progress, message):
            active_jobs[job_id]["progress"] = progress

        result = convert_video(request.input_path, request.output_path, preset, update_progress)
        active_jobs[job_id]["status"] = "completed" if result["success"] else "failed"
        active_jobs[job_id]["result"] = result

    background_tasks.add_task(run_conversion)

    return {"job_id": job_id, "status": "started"}


@router.post("/detect-gopro")
async def detect_gopro(request: ScanRequest):
    """Scan a folder specifically for GoPro files"""
    path = request.path

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")

    gopro_files = []
    total_size = 0

    for root, dirs, filenames in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in VIDEO_EXTENSIONS:
                continue

            filepath = os.path.join(root, filename)

            if is_gopro_file(filepath):
                try:
                    size = os.path.getsize(filepath)
                    total_size += size
                except OSError:
                    size = 0

                gopro_files.append({
                    "filename": filename,
                    "path": filepath,
                    "size": size,
                })

    return {
        "path": path,
        "gopro_files": gopro_files,
        "count": len(gopro_files),
        "total_size": total_size,
    }


@router.get("/disk-space")
async def get_disk_space(path: str = None):
    """Get disk space information for a path"""
    if path is None:
        path = get_library_path()

    # Get the drive root from the path
    if os.path.exists(path):
        drive = os.path.splitdrive(path)[0] or path
    else:
        # Try to get drive from parent paths
        test_path = path
        while test_path and not os.path.exists(test_path):
            parent = os.path.dirname(test_path)
            if parent == test_path:
                break
            test_path = parent
        drive = os.path.splitdrive(test_path)[0] if test_path else "C:"

    try:
        if drive:
            # Add backslash for Windows drive letters
            if len(drive) == 2 and drive[1] == ':':
                drive = drive + '\\'
            usage = shutil.disk_usage(drive)
            return {
                "path": path,
                "drive": drive,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent_used": (usage.used / usage.total) * 100,
            }
    except Exception as e:
        return {
            "path": path,
            "error": str(e),
        }

    return {"path": path, "error": "Could not determine disk space"}


class ImportRequestV2(BaseModel):
    """Enhanced import request with all v1 features"""
    source_path: str
    project_name: str
    file_prefix: str = ""
    notes: str = ""
    organize: bool = True
    convert_gopro: bool = True
    conversion_preset: str = "dnxhd_1080p"
    delete_originals: bool = False
    add_to_existing: bool = False
    selected_dates: List[str] = []  # Filter to only import files from these dates (empty = all)


@router.post("/import-v2")
async def import_files_v2(request: ImportRequestV2, background_tasks: BackgroundTasks):
    """Import files with full v1 feature parity"""
    source_path = request.source_path
    project_name = request.project_name
    library_path = get_library_path()

    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail=f"Source path not found: {source_path}")

    project_path = os.path.join(library_path, project_name)

    # Create subdirectories
    for subdir in PROJECT_SUBDIRS:
        os.makedirs(os.path.join(project_path, subdir), exist_ok=True)

    # Get starting file numbers for each category
    def get_next_file_number(folder_path, prefix):
        if not os.path.exists(folder_path) or not prefix:
            return 1
        max_num = 0
        for filename in os.listdir(folder_path):
            if filename.startswith('.'):
                continue
            name = os.path.splitext(filename)[0]
            if name.startswith(prefix + '_'):
                parts = name.rsplit('_', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    max_num = max(max_num, int(parts[1]))
        return max_num + 1

    counters = {}
    for subdir in PROJECT_SUBDIRS:
        counters[subdir] = get_next_file_number(
            os.path.join(project_path, subdir),
            request.file_prefix
        )

    # Load or create metadata
    metadata_path = os.path.join(project_path, ".metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        metadata["last_import"] = datetime.now().isoformat()
        if request.notes:
            metadata["notes"] = request.notes
    else:
        metadata = {
            "notes": request.notes,
            "created": datetime.now().isoformat(),
            "project_name": project_name,
            "culled_files": [],
            "session_notes": [],
            "import_source": source_path,
            "last_import": datetime.now().isoformat(),
        }

    # Scan and organize files
    imported = {"RAW": 0, "JPEG": 0, "Video": 0, "Other": 0}
    gopro_files = []
    errors = []

    print(f"[Import] Starting import from {source_path}")
    print(f"[Import] Project: {project_name}, Prefix: {request.file_prefix}")

    # Date filtering setup
    selected_dates_set = set(request.selected_dates) if request.selected_dates else None
    if selected_dates_set:
        print(f"[Import] Date filter active: {selected_dates_set}")

    def get_file_date(filepath, ext):
        """Get file date (EXIF for images, mtime for others)"""
        try:
            mtime = os.path.getmtime(filepath)
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")

            # Try EXIF for JPEGs
            if ext in IMAGE_EXTENSIONS:
                try:
                    from PIL import Image
                    from PIL.ExifTags import TAGS
                    with Image.open(filepath) as img:
                        exif = img._getexif()
                        if exif:
                            for tag_id, value in exif.items():
                                tag = TAGS.get(tag_id, tag_id)
                                if tag == "DateTimeOriginal":
                                    date_str = value.split(" ")[0].replace(":", "-")
                                    break
                except Exception:
                    pass
            return date_str
        except Exception:
            return None

    file_count = 0
    skipped_by_date = 0
    for root, dirs, filenames in os.walk(source_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in filenames:
            if filename.startswith("."):
                continue

            filepath = os.path.join(root, filename)
            ext = os.path.splitext(filename)[1].lower()
            stem = os.path.splitext(filename)[0]

            # Skip already converted files
            if '_dnxhd' in stem.lower():
                continue

            # Date filter check (for images only)
            if selected_dates_set and ext in (IMAGE_EXTENSIONS | RAW_EXTENSIONS):
                file_date = get_file_date(filepath, ext)
                if file_date and file_date not in selected_dates_set:
                    skipped_by_date += 1
                    continue

            file_count += 1

            # Determine destination subdirectory and check for GoPro
            if ext in RAW_EXTENSIONS:
                dest_subdir = "RAW"
            elif ext in IMAGE_EXTENSIONS:
                dest_subdir = "JPEG"
            elif ext in VIDEO_EXTENSIONS:
                dest_subdir = "Video"
                # Check if GoPro
                if is_gopro_file(filepath):
                    if request.convert_gopro:
                        gopro_files.append(filepath)
                        print(f"[Import] Queued GoPro for conversion: {filename}")
                        continue  # Will be handled by conversion job
            else:
                dest_subdir = "Other"

            # Generate new filename with prefix
            counter = counters[dest_subdir]
            if request.file_prefix:
                new_filename = f"{request.file_prefix}_{counter:04d}{ext}"
            else:
                new_filename = filename

            dest_path = os.path.join(project_path, dest_subdir, new_filename)

            # Handle duplicates
            dup_counter = 1
            base_new_name = os.path.splitext(new_filename)[0]
            while os.path.exists(dest_path):
                new_filename = f"{base_new_name}_{dup_counter}{ext}"
                dest_path = os.path.join(project_path, dest_subdir, new_filename)
                dup_counter += 1

            try:
                print(f"[Import] Copying {filename} -> {dest_subdir}/{new_filename}")
                if request.delete_originals:
                    shutil.move(filepath, dest_path)
                else:
                    shutil.copy2(filepath, dest_path)
                imported[dest_subdir] += 1
                counters[dest_subdir] += 1
            except Exception as e:
                print(f"[Import] ERROR copying {filename}: {e}")
                errors.append({"file": filename, "error": str(e)})

    print(f"[Import] Done! Copied {sum(imported.values())} files, {len(gopro_files)} GoPro queued for conversion, {skipped_by_date} skipped by date filter")

    # Save metadata
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Start GoPro conversion if needed
    job_id = None
    if gopro_files and request.convert_gopro:
        job_id = f"gopro_{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "current_file": None,
            "completed": 0,
            "total": len(gopro_files),
            "errors": [],
        }

        background_tasks.add_task(
            run_gopro_conversion,
            job_id,
            gopro_files,
            project_path,
            request.file_prefix,
            counters["Video"],
            request.conversion_preset,
            request.delete_originals,
        )

    return {
        "success": True,
        "project_path": project_path,
        "imported": imported,
        "gopro_queued": len(gopro_files),
        "errors": errors,
        "conversion_job_id": job_id,
    }


def run_gopro_conversion(
    job_id: str,
    gopro_files: list,
    project_path: str,
    file_prefix: str,
    start_counter: int,
    preset_name: str,
    delete_originals: bool,
):
    """Background task to convert GoPro files"""
    print(f"[Conversion] Starting job {job_id} with {len(gopro_files)} files")
    job = active_jobs[job_id]
    job["status"] = "running"

    video_dir = os.path.join(project_path, "Video")

    try:
        preset = ConversionPreset(preset_name)
    except ValueError:
        preset = ConversionPreset.DNXHD_1080P

    settings = PRESETS[preset]
    counter = start_counter
    print(f"[Conversion] Using preset: {preset_name}, extension: {settings.extension}")

    total_files = len(gopro_files)

    for i, input_path in enumerate(gopro_files):
        if file_prefix:
            output_filename = f"{file_prefix}_{counter:04d}{settings.extension}"
        else:
            output_filename = os.path.splitext(os.path.basename(input_path))[0] + settings.extension

        output_path = os.path.join(video_dir, output_filename)

        job["current_file"] = os.path.basename(input_path)
        current_file_name = os.path.basename(input_path)
        print(f"[Conversion] [{i+1}/{total_files}] Converting {current_file_name} -> {output_filename}")

        # Create progress callback with captured values (not references)
        def make_progress_callback(file_index, file_name, total, job_dict, jid):
            def update_progress(progress, message):
                file_progress = (file_index + (progress / 100)) / total * 100
                job_dict["progress"] = file_progress
                job_dict["current_message"] = message
                print(f"[Callback] Job {jid}: file_progress={file_progress:.1f}%, ffmpeg_progress={progress:.1f}%")
            return update_progress

        progress_cb = make_progress_callback(i, current_file_name, total_files, job, job_id)
        result = convert_video(input_path, output_path, preset, progress_cb)

        if result["success"]:
            print(f"[Conversion] SUCCESS: {output_filename}")
            job["completed"] += 1
            counter += 1
            if delete_originals:
                try:
                    os.remove(input_path)
                except Exception:
                    pass
        else:
            print(f"[Conversion] FAILED: {os.path.basename(input_path)} - {result.get('error', 'Unknown error')}")
            job["errors"].append({
                "file": os.path.basename(input_path),
                "error": result.get("error", "Unknown error")
            })

        job["progress"] = ((i + 1) / total_files) * 100

    job["status"] = "completed"
    job["current_file"] = None
    print(f"[Conversion] Job {job_id} completed. {job['completed']}/{total_files} successful")


@router.get("/project-info/{name}")
async def get_project_info(name: str):
    """Get info about an existing project for 'add to existing' feature"""
    library_path = get_library_path()
    project_path = os.path.join(library_path, name)

    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail=f"Project not found: {name}")

    metadata_path = os.path.join(project_path, ".metadata.json")
    metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

    # Detect file prefix from existing files
    detected_prefix = ""
    for subdir in PROJECT_SUBDIRS:
        subdir_path = os.path.join(project_path, subdir)
        if os.path.exists(subdir_path):
            files = [f for f in os.listdir(subdir_path) if not f.startswith('.')]
            if files:
                first_file = files[0]
                name_part = os.path.splitext(first_file)[0]
                parts = name_part.rsplit('_', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    detected_prefix = parts[0]
                    break

    return {
        "name": name,
        "path": project_path,
        "metadata": metadata,
        "detected_prefix": detected_prefix,
    }
