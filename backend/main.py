"""
Bridge Burner v2 - FastAPI Backend
Photo culling and organization tool
"""
import os
import webbrowser
import threading
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from config import get_config
from routers import projects
from routers import imports

app = FastAPI(title="Bridge Burner", version="2.0.0")

# Include routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(imports.router, prefix="/api/import", tags=["import"])

# Get the frontend directory path
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


if __name__ == "__main__":
    # Open browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Run the server
    uvicorn.run(app, host="127.0.0.1", port=8000)
