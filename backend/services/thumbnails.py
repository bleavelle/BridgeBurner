"""
Thumbnail generation for Bridge Burner v2
Supports JPEG/PNG and RAW files
"""
import os
import hashlib
from typing import Optional

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import rawpy
    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import THUMBNAIL_SIZE, THUMBNAIL_QUALITY, RAW_EXTENSIONS


def get_thumbnail_dir(project_path: str) -> str:
    """Get the thumbnail cache directory for a project"""
    thumb_dir = os.path.join(project_path, ".thumbnails")
    if not os.path.exists(thumb_dir):
        os.makedirs(thumb_dir, exist_ok=True)
    return thumb_dir


def get_thumbnail_filename(filepath: str) -> str:
    """Generate a unique thumbnail filename based on file path and mtime"""
    try:
        mtime = os.stat(filepath).st_mtime
    except Exception:
        mtime = 0

    # Create hash of path + mtime for cache invalidation
    hash_input = f"{filepath}:{mtime}"
    file_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]

    basename = os.path.splitext(os.path.basename(filepath))[0]
    return f"{basename}_{file_hash}.jpg"


def create_thumbnail_from_image(filepath: str, thumb_path: str) -> bool:
    """Create thumbnail from a standard image file (JPEG, PNG, etc.)"""
    if not HAS_PIL:
        return False

    try:
        with Image.open(filepath) as img:
            # Handle EXIF rotation
            try:
                from PIL import ExifTags
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == "Orientation":
                        break

                exif = img._getexif()
                if exif is not None:
                    orientation_value = exif.get(orientation)
                    if orientation_value == 3:
                        img = img.rotate(180, expand=True)
                    elif orientation_value == 6:
                        img = img.rotate(270, expand=True)
                    elif orientation_value == 8:
                        img = img.rotate(90, expand=True)
            except Exception:
                pass

            # Convert to RGB if necessary
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Create thumbnail
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            img.save(thumb_path, "JPEG", quality=THUMBNAIL_QUALITY)
            return True

    except Exception as e:
        print(f"Error creating thumbnail for {filepath}: {e}")
        return False


def create_thumbnail_from_raw(filepath: str, thumb_path: str) -> bool:
    """Create thumbnail from a RAW file using rawpy"""
    if not HAS_RAWPY or not HAS_PIL:
        return False

    try:
        with rawpy.imread(filepath) as raw:
            # Try to get embedded thumbnail first (faster)
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    with open(thumb_path, "wb") as f:
                        f.write(thumb.data)

                    # Resize if too large
                    with Image.open(thumb_path) as img:
                        if img.size[0] > THUMBNAIL_SIZE[0] or img.size[1] > THUMBNAIL_SIZE[1]:
                            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                            img.save(thumb_path, "JPEG", quality=THUMBNAIL_QUALITY)
                    return True
                elif thumb.format == rawpy.ThumbFormat.BITMAP:
                    img = Image.fromarray(thumb.data)
                    img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                    img.save(thumb_path, "JPEG", quality=THUMBNAIL_QUALITY)
                    return True
            except Exception:
                pass

            # Fall back to full processing (slower but works for all RAW files)
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=True,  # Faster processing
                no_auto_bright=False,
            )
            img = Image.fromarray(rgb)
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            img.save(thumb_path, "JPEG", quality=THUMBNAIL_QUALITY)
            return True

    except Exception as e:
        print(f"Error creating RAW thumbnail for {filepath}: {e}")
        return False


def get_or_create_thumbnail(filepath: str, project_path: str) -> Optional[str]:
    """
    Get or create a thumbnail for a file.
    Returns the thumbnail path, or None if thumbnail cannot be created.
    """
    ext = os.path.splitext(filepath)[1].lower()

    # Check if we can handle this file type
    is_raw = ext in RAW_EXTENSIONS
    if not is_raw and not HAS_PIL:
        return None

    # Get thumbnail path
    thumb_dir = get_thumbnail_dir(project_path)
    thumb_filename = get_thumbnail_filename(filepath)
    thumb_path = os.path.join(thumb_dir, thumb_filename)

    # Return existing thumbnail if it exists
    if os.path.exists(thumb_path):
        return thumb_path

    # Create new thumbnail
    if is_raw:
        if create_thumbnail_from_raw(filepath, thumb_path):
            return thumb_path
    else:
        if create_thumbnail_from_image(filepath, thumb_path):
            return thumb_path

    return None


# Preview settings (larger than thumbnails, for lightbox view)
PREVIEW_MAX_SIZE = (2000, 2000)
PREVIEW_QUALITY = 90


def get_preview_dir(project_path: str) -> str:
    """Get the preview cache directory for a project"""
    preview_dir = os.path.join(project_path, ".previews")
    if not os.path.exists(preview_dir):
        os.makedirs(preview_dir, exist_ok=True)
    return preview_dir


def get_preview_filename(filepath: str) -> str:
    """Generate a unique preview filename based on file path and mtime"""
    try:
        mtime = os.stat(filepath).st_mtime
    except Exception:
        mtime = 0

    hash_input = f"{filepath}:{mtime}"
    file_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]

    basename = os.path.splitext(os.path.basename(filepath))[0]
    return f"{basename}_{file_hash}_preview.jpg"


def create_preview_from_raw(filepath: str, preview_path: str) -> bool:
    """Create a full-size preview JPEG from a RAW file"""
    if not HAS_RAWPY or not HAS_PIL:
        return False

    try:
        with rawpy.imread(filepath) as raw:
            # Try embedded preview first (much faster, usually full resolution)
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    # Embedded JPEG - often full size or close to it
                    with open(preview_path, "wb") as f:
                        f.write(thumb.data)
                    return True
                elif thumb.format == rawpy.ThumbFormat.BITMAP:
                    img = Image.fromarray(thumb.data)
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.save(preview_path, "JPEG", quality=PREVIEW_QUALITY)
                    return True
            except Exception:
                pass

            # Fall back to full RAW processing
            rgb = raw.postprocess(
                use_camera_wb=True,
                half_size=False,  # Full resolution
                no_auto_bright=False,
            )
            img = Image.fromarray(rgb)
            # Resize if massive (some RAWs are 50+ megapixels)
            if img.size[0] > PREVIEW_MAX_SIZE[0] or img.size[1] > PREVIEW_MAX_SIZE[1]:
                img.thumbnail(PREVIEW_MAX_SIZE, Image.Resampling.LANCZOS)
            img.save(preview_path, "JPEG", quality=PREVIEW_QUALITY)
            return True

    except Exception as e:
        print(f"Error creating RAW preview for {filepath}: {e}")
        return False


def get_or_create_preview(filepath: str, project_path: str) -> Optional[str]:
    """
    Get or create a full-size preview for a RAW file.
    Returns the preview path, or None if preview cannot be created.
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext not in RAW_EXTENSIONS:
        return None

    if not HAS_RAWPY:
        return None

    # Get preview path
    preview_dir = get_preview_dir(project_path)
    preview_filename = get_preview_filename(filepath)
    preview_path = os.path.join(preview_dir, preview_filename)

    # Return existing preview if it exists
    if os.path.exists(preview_path):
        return preview_path

    # Create new preview
    if create_preview_from_raw(filepath, preview_path):
        return preview_path

    return None
