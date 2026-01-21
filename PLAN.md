# Bridge Burner v2 - Development Plan

## Overview
Rebuilding the Bridge Burner photo culling app from Streamlit to FastAPI + vanilla JS.
This makes it a proper PWA that can be bundled into a standalone .exe for distribution.

## Why the rewrite?
- Streamlit is slow (full page rerenders)
- Can't make a real PWA with Streamlit
- Want to distribute to friends who don't have Python
- Better keyboard shortcuts and UX

## Target Users
- Photographers who cancelled Adobe subscriptions
- Need free/open-source alternative to Bridge/Lightroom for culling
- Non-technical users (must be easy to install and run)

## Core Features (in priority order)

### Phase 1: Core Culling (MVP)
- [ ] FastAPI backend with endpoints for:
  - GET /api/projects - list all projects
  - GET /api/projects/{name} - get project details + file list
  - GET /api/projects/{name}/files/{filename} - serve image file
  - GET /api/projects/{name}/thumbnail/{filename} - serve thumbnail
  - POST /api/projects/{name}/cull - mark file as culled
  - POST /api/projects/{name}/keep - unmark file as culled
  - DELETE /api/projects/{name}/culled - delete all culled files
- [ ] Frontend with:
  - Project selector
  - Image grid with thumbnails
  - Lightbox view for full-size images
  - Keyboard shortcuts (arrow keys, X to cull, K to keep)
  - Cull/Keep buttons
  - Delete culled files button
- [ ] 90s retro CSS styling (port from Streamlit version)
- [ ] PWA manifest + service worker

### Phase 2: Import & Conversion
- [ ] Import page to scan source folders
- [ ] File organization (RAW/JPEG/Video/Other subdirs)
- [ ] GoPro detection and ffmpeg conversion to DNxHD
- [ ] Progress tracking for long conversions

### Phase 3: Additional Features
- [ ] Settings page (library location, migration)
- [ ] Notes/metadata editing
- [ ] "Open in GIMP" button for selected images
- [ ] "Open in DaVinci Resolve" for video projects

### Phase 4: Distribution
- [ ] PyInstaller bundling to single .exe
- [ ] Include ffmpeg in bundle (or document as requirement)
- [ ] Auto-open browser on launch
- [ ] Installer/setup script

## Technical Stack
- **Backend**: Python 3.11+, FastAPI, uvicorn
- **Frontend**: Vanilla HTML/CSS/JS (no frameworks)
- **Image handling**: Pillow, rawpy (for RAW thumbnails)
- **Video conversion**: ffmpeg (external)
- **Bundling**: PyInstaller

## File Structure
```
bridge_burner_v2/
├── PLAN.md                 # This file
├── backend/
│   ├── main.py            # FastAPI app entry point
│   ├── config.py          # App configuration
│   ├── routers/
│   │   ├── projects.py    # Project endpoints
│   │   └── settings.py    # Settings endpoints
│   └── services/
│       ├── files.py       # File handling utilities
│       ├── thumbnails.py  # Thumbnail generation
│       └── conversion.py  # ffmpeg wrapper
├── frontend/
│   ├── index.html         # Main SPA
│   ├── manifest.json      # PWA manifest
│   ├── sw.js              # Service worker
│   ├── css/
│   │   └── style.css      # 90s retro styling
│   └── js/
│       ├── app.js         # Main application logic
│       ├── api.js         # API client
│       └── lightbox.js    # Lightbox component
├── requirements.txt
├── run.bat                # Windows launcher
└── build.bat              # PyInstaller build script
```

## Compatibility
- Must read existing `.metadata.json` format from Streamlit version
- Projects from v1 should work in v2 without migration
- Config file location: same as v1 (`.bridge_burner_config.json`)

## Current Status
- [x] Plan created
- [x] Backend scaffolded
  - [x] main.py - FastAPI app with static file serving
  - [x] config.py - Config management (compatible with v1)
  - [x] routers/projects.py - All project endpoints + RAW preview conversion
  - [x] routers/imports.py - Import, scan, convert endpoints
  - [x] services/files.py - File handling utilities
  - [x] services/thumbnails.py - Thumbnail + preview generation (Pillow + rawpy)
  - [x] services/conversion.py - FFmpeg wrapper with multiple presets
- [x] Frontend scaffolded
  - [x] index.html - Main SPA structure with Import view
  - [x] js/api.js - API client
  - [x] js/app.js - Main application logic
  - [x] js/lightbox.js - Lightbox with keyboard shortcuts
  - [x] js/import.js - Import wizard with scan/convert
  - [x] css/style.css - 90s retro styling
  - [x] manifest.json - PWA manifest
  - [x] sw.js - Service worker
- [x] Core culling working
- [x] Import working (with all v1 features)
  - [x] Scan source folders
  - [x] File prefix naming
  - [x] Add to existing project
  - [x] GoPro detection
  - [x] Multiple conversion presets (DNxHD, ProRes, H.264, H.265)
  - [x] Disk space display
  - [x] Delete originals option
- [x] PWA working
- [ ] Bundled as .exe

## Notes
- The Streamlit version is still in use (converting 6k GoPro files)
- Keep both versions working during transition
- Library location: `D:\Documents\Projects`

## How to Run
1. Double-click `run.bat` (creates venv and installs deps on first run)
2. Browser opens to http://localhost:8000
3. Select a project and start culling!
