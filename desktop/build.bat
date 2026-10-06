@echo off
echo AutoReach Desktop — Building .exe...
echo.

cd /d %~dp0..

:: Install dependencies if needed
pip install customtkinter pyinstaller groq requests beautifulsoup4 python-dotenv cryptography

:: Build
pyinstaller ^
  --name "AutoReach" ^
  --onefile ^
  --windowed ^
  --icon "desktop\icon.ico" ^
  --add-data "autoreach_core;autoreach_core" ^
  --add-data "moderation;moderation" ^
  --hidden-import "customtkinter" ^
  --collect-submodules "moderation" ^
  --hidden-import "groq" ^
  --hidden-import "bs4" ^
  --collect-all customtkinter ^
  desktop\app.py

echo.
echo Done! Find your .exe at: dist\AutoReach.exe
pause
