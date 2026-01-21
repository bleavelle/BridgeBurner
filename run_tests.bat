@echo off
cd /d "%~dp0"

:: Check if setup has been run
if not exist ".venv\Scripts\python.exe" (
    echo Bridge Burner has not been set up yet.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

:: Install test dependencies if needed
.venv\Scripts\pip.exe show pytest >nul 2>&1
if errorlevel 1 (
    echo Installing test dependencies...
    .venv\Scripts\pip.exe install pytest httpx
)

:: Run tests
echo.
echo Running tests...
echo.
cd backend
..\.venv\Scripts\python.exe -m pytest tests/ -v

pause
