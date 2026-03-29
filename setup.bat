@echo off
REM Batch file wrapper for Windows users without Git Bash
REM This script detects the shell and runs the appropriate setup

setlocal enabledelayedexpansion

REM Check if bash is available (Git Bash, WSL, MSYS, Cygwin)
where bash >nul 2>&1
if %errorlevel% equ 0 (
    REM Bash exists, use it
    echo Detected bash shell, running setup.sh...
    bash setup.sh %*
    exit /b %errorlevel%
) else (
    REM No bash found
    echo.
    echo ╔════════════════════════════════════════════════════╗
    echo ║  ERROR: Bash shell not found!                      ║
    echo ╚════════════════════════════════════════════════════╝
    echo.
    echo To use this setup script on Windows, you need one of:
    echo.
    echo Option 1: Git Bash (Recommended)
    echo   - Download from: https://git-scm.com/download/win
    echo   - Install Git for Windows (includes Git Bash)
    echo   - Then run: bash setup.sh
    echo.
    echo Option 2: Windows Subsystem for Linux (WSL)
    echo   - PowerShell: wsl --install
    echo   - Then open WSL terminal and run: bash setup.sh
    echo.
    echo Option 3: Manual Setup
    echo   1. Install Python 3.12+
    echo   2. Install Docker Desktop
    echo   3. Create .env file from .env.example
    echo   4. Run: python -m venv .venv
    echo   5. Activate: .venv\Scripts\activate.bat
    echo   6. Install deps: pip install -r requirements.txt
    echo   7. Start Docker: docker-compose up -d
    echo.
    pause
    exit /b 1
)
