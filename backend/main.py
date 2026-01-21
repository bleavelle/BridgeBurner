"""
Bridge Burner v2 - FastAPI Backend
Photo culling and organization tool
"""
import os
import sys
import signal
import webbrowser
import threading
import atexit
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from config import get_config
from routers import projects
from routers import imports


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager for startup/shutdown events"""
    # Startup: Clear preview cache from previous sessions
    imports.clear_preview_cache()
    yield
    # Shutdown: nothing special needed


app = FastAPI(title="Bridge Burner", version="2.0.0", lifespan=lifespan)

# Include routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(imports.router, prefix="/api/import", tags=["import"])

# Get the frontend directory path - handle both dev and PyInstaller bundle
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BUNDLE_DIR = sys._MEIPASS
    FRONTEND_DIR = os.path.join(BUNDLE_DIR, "frontend")
else:
    # Running as script
    BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.dirname(BACKEND_DIR)
    FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

# Mount static files
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page"""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "version": "2.0.0"}


def open_browser():
    """Open browser after a short delay"""
    import time
    time.sleep(1)
    webbrowser.open("http://localhost:8000")


def cleanup_and_exit(*args):
    """Clean shutdown - ensures port is released"""
    print("\nShutting down Bridge Burner...")
    os._exit(0)


if __name__ == "__main__":
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)

    # On Windows, also handle CTRL_CLOSE_EVENT via atexit
    atexit.register(cleanup_and_exit)

    # Open browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Run the server
    # When frozen (exe), disable uvicorn's fancy logging to avoid isatty errors
    if getattr(sys, 'frozen', False):
        uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
    else:
        uvicorn.run(app, host="127.0.0.1", port=8000)
