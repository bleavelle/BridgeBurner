"""
Unit tests for Bridge Burner API endpoints
"""
import os
import sys
import tempfile
import shutil
import json
import pytest
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from config import PROJECT_SUBDIRS

client = TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint"""

    def test_health_check(self):
        """Test health check returns OK"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestRootEndpoint:
    """Tests for root endpoint"""

    def test_root_returns_html(self):
        """Test root serves HTML page"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestProjectsAPI:
    """Tests for projects API endpoints"""

    def test_list_projects(self):
        """Test listing projects"""
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "library_path" in data
        assert isinstance(data["projects"], list)

    def test_get_nonexistent_project(self):
        """Test getting a project that doesn't exist"""
        response = client.get("/api/projects/nonexistent_project_12345")
        assert response.status_code == 404

    def test_cull_without_project(self):
        """Test culling file in nonexistent project"""
        response = client.post(
            "/api/projects/nonexistent_project_12345/cull",
            json={"filename": "test.jpg"}
        )
        assert response.status_code == 404

    def test_keep_without_project(self):
        """Test keeping file in nonexistent project"""
        response = client.post(
            "/api/projects/nonexistent_project_12345/keep",
            json={"filename": "test.jpg"}
        )
        assert response.status_code == 404


class TestImportAPI:
    """Tests for import API endpoints"""

    def test_ffmpeg_status(self):
        """Test ffmpeg status check"""
        response = client.get("/api/import/ffmpeg-status")
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert isinstance(data["available"], bool)

    def test_list_presets(self):
        """Test listing conversion presets"""
        response = client.get("/api/import/presets")
        assert response.status_code == 200
        data = response.json()
        assert "presets" in data
        assert len(data["presets"]) > 0

        # Check preset structure
        preset = data["presets"][0]
        assert "id" in preset
        assert "name" in preset
        assert "description" in preset

    def test_scan_nonexistent_path(self):
        """Test scanning nonexistent path"""
        response = client.post(
            "/api/import/scan",
            json={"path": "/nonexistent/path/12345"}
        )
        assert response.status_code == 404

    def test_scan_valid_path(self):
        """Test scanning a valid temporary path"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test files
            with open(os.path.join(temp_dir, "test.jpg"), "w") as f:
                f.write("fake jpeg")
            with open(os.path.join(temp_dir, "test.mp4"), "w") as f:
                f.write("fake video")

            response = client.post(
                "/api/import/scan",
                json={"path": temp_dir}
            )
            assert response.status_code == 200
            data = response.json()
            assert "counts" in data
            assert "total_size" in data
            assert data["counts"]["total"] >= 2

    def test_disk_space(self):
        """Test disk space check"""
        response = client.get("/api/import/disk-space")
        assert response.status_code == 200
        data = response.json()
        # Should have either space info or error
        assert "path" in data

    def test_list_jobs(self):
        """Test listing conversion jobs"""
        response = client.get("/api/import/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data

    def test_get_nonexistent_job(self):
        """Test getting nonexistent job"""
        response = client.get("/api/import/jobs/nonexistent_job_12345")
        assert response.status_code == 404

    def test_import_nonexistent_source(self):
        """Test importing from nonexistent source"""
        response = client.post(
            "/api/import/import-v2",
            json={
                "source_path": "/nonexistent/path/12345",
                "project_name": "test_project",
                "file_prefix": "test",
            }
        )
        assert response.status_code == 404


class TestProjectWithTempDir:
    """Tests that use a temporary project directory"""

    @pytest.fixture
    def temp_project(self, tmp_path, monkeypatch):
        """Create a temporary project for testing"""
        # Create project structure
        project_name = "test_project"
        project_path = tmp_path / project_name

        for subdir in PROJECT_SUBDIRS:
            (project_path / subdir).mkdir(parents=True)

        # Create metadata
        metadata = {
            "notes": "Test project",
            "created": "2024-01-01T00:00:00",
            "project_name": project_name,
            "culled_files": [],
        }
        with open(project_path / ".metadata.json", "w") as f:
            json.dump(metadata, f)

        # Create test files
        with open(project_path / "JPEG" / "test1.jpg", "w") as f:
            f.write("fake jpeg 1")
        with open(project_path / "JPEG" / "test2.jpg", "w") as f:
            f.write("fake jpeg 2")
        with open(project_path / "RAW" / "test1.cr2", "w") as f:
            f.write("fake raw")

        # Patch the library path where it's imported in the router modules
        # (patching config module doesn't work because routers import directly)
        from routers import projects as projects_router
        monkeypatch.setattr(projects_router, "get_library_path", lambda: str(tmp_path))

        return {
            "name": project_name,
            "path": str(project_path),
            "library_path": str(tmp_path),
        }

    def test_list_projects_with_temp(self, temp_project):
        """Test listing projects includes our temp project"""
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        project_names = [p["name"] for p in data["projects"]]
        assert temp_project["name"] in project_names

    def test_get_project_details(self, temp_project):
        """Test getting project details"""
        response = client.get(f"/api/projects/{temp_project['name']}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == temp_project["name"]
        assert "files" in data
        assert len(data["files"]) == 3  # 2 JPEGs + 1 RAW

    def test_cull_file(self, temp_project):
        """Test culling a file"""
        response = client.post(
            f"/api/projects/{temp_project['name']}/cull",
            json={"filename": "test1.jpg"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "culled"
        assert data["filename"] == "test1.jpg"

    def test_keep_file(self, temp_project):
        """Test keeping a file"""
        # First cull it
        client.post(
            f"/api/projects/{temp_project['name']}/cull",
            json={"filename": "test1.jpg"}
        )

        # Then keep it
        response = client.post(
            f"/api/projects/{temp_project['name']}/keep",
            json={"filename": "test1.jpg"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "kept"

    def test_delete_culled_empty(self, temp_project):
        """Test deleting culled files when none are culled"""
        response = client.delete(f"/api/projects/{temp_project['name']}/culled")
        assert response.status_code == 200
        data = response.json()
        assert data["total_deleted"] == 0

    def test_delete_culled_with_files(self, temp_project):
        """Test deleting culled files"""
        # Cull a file
        client.post(
            f"/api/projects/{temp_project['name']}/cull",
            json={"filename": "test1.jpg"}
        )

        # Delete culled
        response = client.delete(f"/api/projects/{temp_project['name']}/culled")
        assert response.status_code == 200
        data = response.json()
        assert data["total_deleted"] == 1

        # Verify file is gone
        project_path = temp_project["path"]
        assert not os.path.exists(os.path.join(project_path, "JPEG", "test1.jpg"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
