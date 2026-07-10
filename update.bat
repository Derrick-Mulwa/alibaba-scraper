@echo off
setlocal

echo Pulling latest code...
git reset --hard origin/main
git pull origin main

REM 1. Check if Python 3.11 is installed
py -3.11 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python 3.11 not found. Installing via Winget...
    
    REM Install Python 3.11.9 using Winget
    winget install --id Python.Python.3.11 --version 3.11.9 --silent --accept-package-agreements --accept-source-agreements
    
    REM Re-check after installation
    py -3.11 --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo Error: Python 3.11 installation failed or path not yet updated.
        echo Try restarting your CMD window.
        pause
        exit /b
    )
)

REM 2. Ensure Virtual Environment exists
if not exist ".venv" (
    echo Creating virtual environment with Python 3.11...
    py -3.11 -m venv .venv
)

REM 3. Update dependencies
echo Updating dependencies...
.venv\Scripts\python.exe -m pip install -q --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

REM 4. Launch
echo Starting main.py...
.venv\Scripts\python.exe main.py

pause
