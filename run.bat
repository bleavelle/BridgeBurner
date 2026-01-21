@echo off
cd /d "%~dp0"

:: Use the existing photo_organizer venv since Python isn't in PATH
set PYTHON=C:\Users\Edward Buendia\Documents\photo_organizer\.venv\Scripts\python.exe
set PIP=C:\Users\Edward Buendia\Documents\photo_organizer\.venv\Scripts\pip.exe

:: Check if we need to install FastAPI
"%PIP%" show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing FastAPI dependencies...
    "%PIP%" install fastapi uvicorn[standard] pillow rawpy
)

:: Run the FastAPI server
echo Starting Bridge Burner v2...
"%PYTHON%" backend\main.py

pause
