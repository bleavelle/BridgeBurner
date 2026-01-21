"""
Video conversion service using ffmpeg
Supports DNxHD, ProRes, H.264, H.265 output formats
"""
import os
import subprocess
import shutil
import re
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum


class ConversionPreset(Enum):
    """Available conversion presets"""
    DNXHD_1080P = "dnxhd_1080p"
    DNXHD_4K = "dnxhd_4k"
    PRORES_PROXY = "prores_proxy"
    PRORES_LT = "prores_lt"
    PRORES_422 = "prores_422"
    PRORES_HQ = "prores_hq"
    H264_HIGH = "h264_high"
    H264_MEDIUM = "h264_medium"
    H265_HIGH = "h265_high"
    H265_MEDIUM = "h265_medium"
    COPY = "copy"  # Just remux, no transcode


@dataclass
class ConversionSettings:
    """Settings for a conversion preset"""
    name: str
    description: str
    extension: str
    ffmpeg_args: list
    estimated_size_multiplier: float  # Relative to source


# Preset configurations
PRESETS: Dict[ConversionPreset, ConversionSettings] = {
    ConversionPreset.DNXHD_1080P: ConversionSettings(
        name="DNxHD 1080p",
        description="Avid DNxHD for 1080p editing (DaVinci Resolve compatible)",
        extension=".mov",
        ffmpeg_args=[
            "-c:v", "dnxhd",
            "-profile:v", "dnxhr_hq",
            "-pix_fmt", "yuv422p",
            "-c:a", "pcm_s16le",
        ],
        estimated_size_multiplier=17.0,
    ),
    ConversionPreset.DNXHD_4K: ConversionSettings(
        name="DNxHR 4K",
        description="Avid DNxHR for 4K editing (DaVinci Resolve compatible)",
        extension=".mov",
        ffmpeg_args=[
            "-c:v", "dnxhd",
            "-profile:v", "dnxhr_hqx",
            "-pix_fmt", "yuv422p10le",
            "-c:a", "pcm_s16le",
        ],
        estimated_size_multiplier=20.0,
    ),
    ConversionPreset.PRORES_PROXY: ConversionSettings(
        name="ProRes Proxy",
        description="Apple ProRes Proxy - smallest ProRes, good for offline editing",
        extension=".mov",
        ffmpeg_args=[
            "-c:v", "prores_ks",
            "-profile:v", "0",
            "-pix_fmt", "yuv422p10le",
            "-c:a", "pcm_s16le",
        ],
        estimated_size_multiplier=3.0,
    ),
    ConversionPreset.PRORES_LT: ConversionSettings(
        name="ProRes LT",
        description="Apple ProRes LT - good balance of quality and size",
        extension=".mov",
        ffmpeg_args=[
            "-c:v", "prores_ks",
            "-profile:v", "1",
            "-pix_fmt", "yuv422p10le",
            "-c:a", "pcm_s16le",
        ],
        estimated_size_multiplier=6.0,
    ),
    ConversionPreset.PRORES_422: ConversionSettings(
        name="ProRes 422",
        description="Apple ProRes 422 - standard editing quality",
        extension=".mov",
        ffmpeg_args=[
            "-c:v", "prores_ks",
            "-profile:v", "2",
            "-pix_fmt", "yuv422p10le",
            "-c:a", "pcm_s16le",
        ],
        estimated_size_multiplier=10.0,
    ),
    ConversionPreset.PRORES_HQ: ConversionSettings(
        name="ProRes 422 HQ",
        description="Apple ProRes 422 HQ - high quality mastering",
        extension=".mov",
        ffmpeg_args=[
            "-c:v", "prores_ks",
            "-profile:v", "3",
            "-pix_fmt", "yuv422p10le",
            "-c:a", "pcm_s16le",
        ],
        estimated_size_multiplier=15.0,
    ),
    ConversionPreset.H264_HIGH: ConversionSettings(
        name="H.264 High Quality",
        description="H.264/AVC - good for sharing, smaller files",
        extension=".mp4",
        ffmpeg_args=[
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
        ],
        estimated_size_multiplier=0.8,
    ),
    ConversionPreset.H264_MEDIUM: ConversionSettings(
        name="H.264 Medium",
        description="H.264/AVC - balanced quality and size",
        extension=".mp4",
        ffmpeg_args=[
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
        ],
        estimated_size_multiplier=0.5,
    ),
    ConversionPreset.H265_HIGH: ConversionSettings(
        name="H.265 High Quality",
        description="H.265/HEVC - best compression, smaller than H.264",
        extension=".mp4",
        ffmpeg_args=[
            "-c:v", "libx265",
            "-preset", "slow",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
        ],
        estimated_size_multiplier=0.5,
    ),
    ConversionPreset.H265_MEDIUM: ConversionSettings(
        name="H.265 Medium",
        description="H.265/HEVC - good compression, fast encode",
        extension=".mp4",
        ffmpeg_args=[
            "-c:v", "libx265",
            "-preset", "medium",
            "-crf", "25",
            "-c:a", "aac",
            "-b:a", "128k",
        ],
        estimated_size_multiplier=0.3,
    ),
    ConversionPreset.COPY: ConversionSettings(
        name="Copy (Remux)",
        description="Just copy streams to new container, no re-encoding",
        extension=".mov",
        ffmpeg_args=[
            "-c:v", "copy",
            "-c:a", "copy",
        ],
        estimated_size_multiplier=1.0,
    ),
}


def find_ffmpeg() -> Optional[str]:
    """Find ffmpeg executable"""
    # Check if ffmpeg is in PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    # Check common Windows locations
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\ffmpeg\bin\ffmpeg.exe"),
    ]

    for path in common_paths:
        if os.path.exists(path):
            return path

    # Check in app directory
    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bundled_ffmpeg = os.path.join(app_dir, "ffmpeg", "bin", "ffmpeg.exe")
    if os.path.exists(bundled_ffmpeg):
        return bundled_ffmpeg

    return None


def get_ffmpeg_version() -> Optional[str]:
    """Get ffmpeg version string"""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return None

    try:
        result = subprocess.run(
            [ffmpeg, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Extract version from first line
            first_line = result.stdout.split("\n")[0]
            return first_line
    except Exception:
        pass

    return None


def get_video_info(filepath: str) -> Optional[Dict[str, Any]]:
    """Get video file information using ffprobe"""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return None

    # ffprobe is usually next to ffmpeg
    ffprobe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
    if not os.path.exists(ffprobe):
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                filepath,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            import json
            return json.loads(result.stdout)
    except Exception:
        pass

    return None


def is_gopro_file(filepath: str) -> bool:
    """Check if a file is from a GoPro camera"""
    filename = os.path.basename(filepath).upper()

    # GoPro naming patterns: GH010001.MP4, GOPR0001.MP4, GP010001.MP4
    gopro_patterns = [
        r"^GH\d{6}\.MP4$",
        r"^GOPR\d{4}\.MP4$",
        r"^GP\d{6}\.MP4$",
        r"^GX\d{6}\.MP4$",
    ]

    for pattern in gopro_patterns:
        if re.match(pattern, filename):
            return True

    # Also check metadata if available
    info = get_video_info(filepath)
    if info:
        format_info = info.get("format", {})
        tags = format_info.get("tags", {})
        if "GoPro" in tags.get("encoder", "") or "GoPro" in tags.get("handler_name", ""):
            return True

    return False


def convert_video(
    input_path: str,
    output_path: str,
    preset: ConversionPreset = ConversionPreset.DNXHD_1080P,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    """
    Convert a video file using ffmpeg.

    Args:
        input_path: Path to input video
        output_path: Path for output video (extension will be adjusted based on preset)
        preset: Conversion preset to use
        progress_callback: Optional callback(progress_percent, status_message)

    Returns:
        Dict with success status and details
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return {"success": False, "error": "ffmpeg not found"}

    if not os.path.exists(input_path):
        return {"success": False, "error": f"Input file not found: {input_path}"}

    settings = PRESETS[preset]

    # Ensure output has correct extension
    output_base = os.path.splitext(output_path)[0]
    output_path = output_base + settings.extension

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Get input duration for progress tracking
    duration = None
    info = get_video_info(input_path)
    if info:
        format_info = info.get("format", {})
        duration = float(format_info.get("duration", 0))

    # Build ffmpeg command
    cmd = [
        ffmpeg,
        "-y",  # Overwrite output
        "-i", input_path,
        *settings.ffmpeg_args,
        "-progress", "pipe:1",  # Output progress to stdout
        output_path,
    ]

    try:
        print(f"[FFmpeg] Starting: {os.path.basename(input_path)}")
        print(f"[FFmpeg] Duration: {duration}s")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,  # Line buffered for real-time progress
            universal_newlines=True,
        )

        # Parse progress output - use readline() for unbuffered reading
        current_time = 0
        last_print_progress = -1
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            line = line.strip()
            if line.startswith("out_time_ms="):
                try:
                    time_ms = int(line.split("=")[1])
                    current_time = time_ms / 1000000  # Convert to seconds
                    if duration and duration > 0:
                        progress = min(100, (current_time / duration) * 100)
                        # Always call the callback so UI updates
                        if progress_callback:
                            progress_callback(progress, f"Converting... {progress:.1f}%")
                        # Only print to console every 5%
                        if int(progress / 5) > int(last_print_progress / 5):
                            print(f"[FFmpeg] Progress: {progress:.1f}%")
                            last_print_progress = progress
                except ValueError:
                    pass

        process.wait()
        print(f"[FFmpeg] Process finished with code: {process.returncode}")

        if process.returncode == 0:
            return {
                "success": True,
                "output_path": output_path,
                "preset": preset.value,
            }
        else:
            stderr = process.stderr.read() if process.stderr else ""
            return {
                "success": False,
                "error": f"ffmpeg failed: {stderr[:500]}",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_presets_list() -> list:
    """Get list of available presets for the frontend"""
    return [
        {
            "id": preset.value,
            "name": settings.name,
            "description": settings.description,
            "extension": settings.extension,
            "size_multiplier": settings.estimated_size_multiplier,
        }
        for preset, settings in PRESETS.items()
    ]
