@echo off
echo ========================================
echo   Bridge Burner v2 - Build Executable
echo ========================================
echo.

cd /d "%~dp0"

:: Check if setup has been run
if not exist ".venv\Scripts\python.exe" (
    echo Please run setup.bat first!
    pause
    exit /b 1
)

:: Install PyInstaller if needed
.venv\Scripts\pip.exe show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    .venv\Scripts\pip.exe install pyinstaller
)

:: Build the executable
echo.
echo Building executable...
echo This may take a few minutes...
echo.

.venv\Scripts\pyinstaller.exe --onedir --console --name "BridgeBurner" ^
    --add-data "frontend;frontend" ^
    --add-data "ffmpeg;ffmpeg" ^
    --hidden-import uvicorn.logging ^
    --hidden-import uvicorn.protocols.http ^
    --hidden-import uvicorn.protocols.http.auto ^
    --hidden-import uvicorn.protocols.websockets ^
    --hidden-import uvicorn.protocols.websockets.auto ^
    --hidden-import uvicorn.lifespan ^
    --hidden-import uvicorn.lifespan.on ^
    --hidden-import uvicorn.loops ^
    --hidden-import uvicorn.loops.auto ^
    --hidden-import email.mime.text ^
    --collect-submodules uvicorn ^
    --collect-submodules fastapi ^
    --collect-submodules starlette ^
    backend\main.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build complete!
echo ========================================
echo.
echo Executable is in: dist\BridgeBurner\
echo.
echo You can zip up the BridgeBurner folder and send it to anyone!
echo.
pause
