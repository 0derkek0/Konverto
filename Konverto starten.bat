@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Erster Start: richte Konverto ein, einen Moment...
    python -m venv .venv || (echo Python wurde nicht gefunden. Bitte Python 3.10+ installieren. & pause & exit /b 1)
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (pause & exit /b 1)
)
start "" ".venv\Scripts\pythonw.exe" Konverto.pyw %*
