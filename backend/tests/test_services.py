"""
Unit tests for Bridge Burner services
"""
import os
import sys
import tempfile
import shutil
import pytest

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    IMAGE_EXTENSIONS,
    RAW_EXTENSIONS,
    VIDEO_EXTENSIONS,
    PROJECT_SUBDIRS,
    get_config,
    get_library_path,
)
from services.files import get_file_type, get_file_info, get_project_files, format_file_size
from services.conversion import (
    ConversionPreset,
    PRESETS,
    find_ffmpeg,
    estimate_conversion_time,
    is_gopro_file,
    get_presets_list,
)


class TestConfig:
    """Tests for configuration module"""

    def test_project_subdirs_exist(self):
        """Ensure project subdirectories are defined"""
        assert len(PROJECT_SUBDIRS) > 0
        assert "RAW" in PROJECT_SUBDIRS
        assert "JPEG" in PROJECT_SUBDIRS
        assert "Video" in PROJECT_SUBDIRS

    def test_image_extensions_defined(self):
        """Ensure image extensions are defined"""
        assert ".jpg" in IMAGE_EXTENSIONS
        assert ".jpeg" in IMAGE_EXTENSIONS
        assert ".png" in IMAGE_EXTENSIONS

    def test_raw_extensions_defined(self):
        """Ensure RAW extensions are defined"""
        assert ".cr2" in RAW_EXTENSIONS
        assert ".nef" in RAW_EXTENSIONS
        assert ".arw" in RAW_EXTENSIONS

    def test_video_extensions_defined(self):
        """Ensure video extensions are defined"""
        assert ".mp4" in VIDEO_EXTENSIONS
        assert ".mov" in VIDEO_EXTENSIONS

    def test_get_config_returns_dict(self):
        """Config should return a dictionary"""
        config = get_config()
        assert isinstance(config, dict)

    def test_get_library_path_returns_string(self):
        """Library path should return a string"""
        path = get_library_path()
        assert isinstance(path, str)
        assert len(path) > 0


class TestFileService:
    """Tests for file service"""

    def test_get_file_type_image(self):
        """Test image file type detection"""
        assert get_file_type("photo.jpg") == "image"
        assert get_file_type("photo.JPEG") == "image"
        assert get_file_type("photo.png") == "image"

    def test_get_file_type_raw(self):
        """Test RAW file type detection"""
        assert get_file_type("photo.cr2") == "raw"
        assert get_file_type("photo.CR2") == "raw"
        assert get_file_type("photo.nef") == "raw"
        assert get_file_type("photo.arw") == "raw"

    def test_get_file_type_video(self):
        """Test video file type detection"""
        assert get_file_type("video.mp4") == "video"
        assert get_file_type("video.MP4") == "video"
        assert get_file_type("video.mov") == "video"

    def test_get_file_type_other(self):
        """Test other file type detection"""
        assert get_file_type("document.txt") == "other"
        assert get_file_type("data.json") == "other"

    def test_format_file_size(self):
        """Test file size formatting"""
        assert "B" in format_file_size(500)
        assert "KB" in format_file_size(5000)
        assert "MB" in format_file_size(5000000)
        assert "GB" in format_file_size(5000000000)

    def test_get_file_info_with_temp_file(self):
        """Test getting file info from a real file"""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            info = get_file_info(temp_path)
            assert info["filename"].endswith(".jpg")
            assert info["type"] == "image"
            assert info["size"] > 0
            assert info["can_thumbnail"] == True
        finally:
            os.unlink(temp_path)

    def test_get_project_files_empty(self):
        """Test getting files from empty project"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create project structure
            for subdir in PROJECT_SUBDIRS:
                os.makedirs(os.path.join(temp_dir, subdir))

            files = get_project_files(temp_dir)
            assert files == []

    def test_get_project_files_with_content(self):
        """Test getting files from project with content"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create project structure
            for subdir in PROJECT_SUBDIRS:
                os.makedirs(os.path.join(temp_dir, subdir))

            # Add test files
            with open(os.path.join(temp_dir, "RAW", "test.cr2"), "w") as f:
                f.write("fake raw")
            with open(os.path.join(temp_dir, "JPEG", "test.jpg"), "w") as f:
                f.write("fake jpeg")

            files = get_project_files(temp_dir)
            assert len(files) == 2

    def test_get_project_files_ignores_hidden(self):
        """Test that hidden files are ignored"""
        with tempfile.TemporaryDirectory() as temp_dir:
            for subdir in PROJECT_SUBDIRS:
                os.makedirs(os.path.join(temp_dir, subdir))

            # Add hidden file
            with open(os.path.join(temp_dir, "JPEG", ".hidden.jpg"), "w") as f:
                f.write("hidden")
            with open(os.path.join(temp_dir, "JPEG", "visible.jpg"), "w") as f:
                f.write("visible")

            files = get_project_files(temp_dir)
            assert len(files) == 1
            assert "visible.jpg" in files[0]


class TestConversionService:
    """Tests for video conversion service"""

    def test_presets_defined(self):
        """Ensure conversion presets are defined"""
        assert len(PRESETS) > 0
        assert ConversionPreset.DNXHD_1080P in PRESETS
        assert ConversionPreset.PRORES_422 in PRESETS
        assert ConversionPreset.H264_HIGH in PRESETS

    def test_preset_settings_complete(self):
        """Ensure all presets have required settings"""
        for preset, settings in PRESETS.items():
            assert settings.name, f"{preset} missing name"
            assert settings.description, f"{preset} missing description"
            assert settings.extension, f"{preset} missing extension"
            assert isinstance(settings.ffmpeg_args, list), f"{preset} ffmpeg_args not list"
            assert settings.estimated_size_multiplier > 0, f"{preset} invalid size multiplier"
            assert settings.estimated_speed > 0, f"{preset} invalid speed"

    def test_estimate_conversion_time(self):
        """Test conversion time estimation"""
        # 60 second video with DNxHD (speed 0.8) should take ~75 seconds
        duration = 60
        estimated = estimate_conversion_time(duration, ConversionPreset.DNXHD_1080P)
        assert estimated > 0
        assert estimated == duration / PRESETS[ConversionPreset.DNXHD_1080P].estimated_speed

    def test_estimate_conversion_time_copy(self):
        """Copy preset should be very fast"""
        duration = 60
        estimated = estimate_conversion_time(duration, ConversionPreset.COPY)
        # Copy is 10x real-time, so 60s video = 6s
        assert estimated < duration

    def test_is_gopro_file_patterns(self):
        """Test GoPro filename detection"""
        # GoPro patterns
        assert is_gopro_file("GH010001.MP4") == True
        assert is_gopro_file("GOPR0001.MP4") == True
        assert is_gopro_file("GP010001.MP4") == True
        assert is_gopro_file("GX010001.MP4") == True

        # Non-GoPro
        assert is_gopro_file("video.mp4") == False
        assert is_gopro_file("DSC_0001.MOV") == False

    def test_get_presets_list(self):
        """Test getting presets as list for frontend"""
        presets = get_presets_list()
        assert isinstance(presets, list)
        assert len(presets) == len(PRESETS)

        for preset in presets:
            assert "id" in preset
            assert "name" in preset
            assert "description" in preset
            assert "extension" in preset

    def test_find_ffmpeg(self):
        """Test ffmpeg detection"""
        # This may or may not find ffmpeg depending on environment
        result = find_ffmpeg()
        # Just verify it returns string or None
        assert result is None or isinstance(result, str)


class TestThumbnailService:
    """Tests for thumbnail service"""

    def test_thumbnail_imports(self):
        """Test that thumbnail module imports correctly"""
        from services.thumbnails import (
            get_thumbnail_dir,
            get_thumbnail_filename,
            get_or_create_thumbnail,
            THUMBNAIL_SIZE,
            THUMBNAIL_QUALITY,
        )

        assert THUMBNAIL_SIZE == (300, 300)
        assert THUMBNAIL_QUALITY == 85

    def test_get_thumbnail_dir(self):
        """Test thumbnail directory creation"""
        from services.thumbnails import get_thumbnail_dir

        with tempfile.TemporaryDirectory() as temp_dir:
            thumb_dir = get_thumbnail_dir(temp_dir)
            assert os.path.exists(thumb_dir)
            assert thumb_dir.endswith(".thumbnails")

    def test_get_thumbnail_filename(self):
        """Test thumbnail filename generation"""
        from services.thumbnails import get_thumbnail_filename

        # Create a temp file to test with
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name

        try:
            filename = get_thumbnail_filename(temp_path)
            assert filename.endswith(".jpg")
            assert "_" in filename  # Contains hash
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
