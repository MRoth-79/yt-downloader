@echo off
setlocal
cd /d "%~dp0"

rem Create a project-local virtual environment on first run so packages are not installed globally.
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo Could not create the virtual environment.
        echo Make sure Python 3.10 or newer is installed and available on PATH.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" run.py
pause
