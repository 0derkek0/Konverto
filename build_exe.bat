@echo off
rem Baut die eigenstaendige Konverto.exe nach dist\Konverto\
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
)
".venv\Scripts\python.exe" packaging\build.py || (pause & exit /b 1)
echo.
echo Fertig: dist\Konverto\Konverto.exe  (den ganzen Ordner dist\Konverto weitergeben)
pause
