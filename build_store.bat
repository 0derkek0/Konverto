@echo off
rem Baut das MSIX-Paket fuer den Microsoft Store nach dist\Konverto_<version>_x64.msix
rem Vorher packaging\store_config.json mit den Werten aus Partner Center fuellen (siehe STORE.md).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
)
".venv\Scripts\python.exe" packaging\build.py --msix %* || (pause & exit /b 1)
echo.
echo Fertig: Die .msix-Datei in dist\ in Partner Center hochladen.
pause
