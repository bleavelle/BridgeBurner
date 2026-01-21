@echo off
echo ========================================
echo  FFmpeg Setup for Bridge Burner
echo ========================================
echo.

cd /d "%~dp0"

:: Check if ffmpeg already exists
if exist "ffmpeg\bin\ffmpeg.exe" (
    echo FFmpeg is already installed!
    ffmpeg\bin\ffmpeg.exe -version
    echo.
    pause
    exit /b 0
)

:: Check for curl (comes with Windows 10+)
where curl >nul 2>&1
if errorlevel 1 (
    echo ERROR: curl not found. Please install curl or download ffmpeg manually.
    echo Download from: https://www.gyan.dev/ffmpeg/builds/
    pause
    exit /b 1
)

echo Downloading FFmpeg...
echo This may take a few minutes depending on your connection.
echo.

:: Download ffmpeg essentials build (smaller, has what we need)
curl -L -o ffmpeg.zip "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

if errorlevel 1 (
    echo.
    echo ERROR: Download failed!
    echo Please download manually from: https://www.gyan.dev/ffmpeg/builds/
    echo Extract to: %~dp0ffmpeg\
    pause
    exit /b 1
)

echo.
echo Extracting FFmpeg...

:: Use PowerShell to extract (available on all modern Windows)
powershell -command "Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'ffmpeg_temp' -Force"

if errorlevel 1 (
    echo.
    echo ERROR: Extraction failed!
    echo Please extract ffmpeg.zip manually to the ffmpeg folder.
    pause
    exit /b 1
)

:: Move contents from nested folder to ffmpeg
for /d %%i in (ffmpeg_temp\ffmpeg-*) do (
    if exist "ffmpeg" rmdir /s /q "ffmpeg"
    move "%%i" "ffmpeg"
)

:: Cleanup
rmdir /s /q "ffmpeg_temp" 2>nul
del ffmpeg.zip 2>nul

:: Verify installation
if exist "ffmpeg\bin\ffmpeg.exe" (
    echo.
    echo ========================================
    echo  FFmpeg installed successfully!
    echo ========================================
    echo.
    ffmpeg\bin\ffmpeg.exe -version
    echo.
    echo You can now use video conversion in Bridge Burner.
) else (
    echo.
    echo ERROR: Installation verification failed.
    echo Please download ffmpeg manually from: https://www.gyan.dev/ffmpeg/builds/
)

echo.
pause
