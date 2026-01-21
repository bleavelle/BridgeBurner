@echo off
echo ========================================
echo   Bridge Burner v2 - Setup
echo ========================================
echo.

cd /d "%~dp0"

:: Check for Python in common locations
set PYTHON_FOUND=0

:: Try py launcher (most reliable on Windows)
where py >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    set PYTHON_FOUND=1
    goto :found
)

:: Try python in PATH
where python >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    set PYTHON_FOUND=1
    goto :found
)

:: Check common install locations
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    set PYTHON_FOUND=1
    goto :found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    set PYTHON_FOUND=1
    goto :found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    set PYTHON_FOUND=1
    goto :found
)
if exist "C:\Python312\python.exe" (
    set PYTHON_CMD="C:\Python312\python.exe"
    set PYTHON_FOUND=1
    goto :found
)
if exist "C:\Python311\python.exe" (
    set PYTHON_CMD="C:\Python311\python.exe"
    set PYTHON_FOUND=1
    goto :found
)

:: Python not found
echo ERROR: Python not found!
echo.
echo Please install Python 3.10 or newer:
echo   https://www.python.org/downloads/
echo.
echo IMPORTANT: During installation, check the box that says:
echo   [x] Add Python to PATH
echo.
echo After installing Python, run this setup again.
echo.
pause
exit /b 1

:found
echo Found Python: %PYTHON_CMD%
echo.

:: Delete old broken venv if pip doesn't exist
if exist ".venv" (
    if not exist ".venv\Scripts\pip.exe" (
        echo Removing broken virtual environment...
        rmdir /s /q .venv
    )
)

:: Create virtual environment
if exist ".venv\Scripts\python.exe" (
    echo Virtual environment already exists.
) else (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment!
        pause
        exit /b 1
    )
)

:: Install dependencies
echo.
echo Installing dependencies...
.venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Setup complete!
echo ========================================
echo.
echo To run Bridge Burner, double-click: run.bat
echo.
pause
