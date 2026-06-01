@echo off
echo AutoReach Desktop — Building .exe...
echo.

cd /d %~dp0..

:: Install dependencies if needed
pip install customtkinter pyinstaller groq requests beautifulsoup4 python-dotenv

:: Build
pyinstaller ^
  --name "AutoReach" ^
  --onefile ^
  --windowed ^
  --icon "desktop\icon.ico" ^
  --add-data "autoreach_core;autoreach_core" ^
  --hidden-import "customtkinter" ^
  --hidden-import "groq" ^
  --hidden-import "bs4" ^
  --collect-all customtkinter ^
  desktop\app.py

echo.
echo Done! Find your .exe at: dist\AutoReach.exe
pause
