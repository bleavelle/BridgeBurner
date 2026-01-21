@echo off
cd /d "%~dp0"

:: Check if setup has been run
if not exist ".venv\Scripts\python.exe" (
    echo Bridge Burner has not been set up yet.
    echo.
    echo Running setup...
    call setup.bat
    if errorlevel 1 exit /b 1
)

:: Run the app
echo Starting Bridge Burner v2...
.venv\Scripts\python.exe backend\main.py

pause
