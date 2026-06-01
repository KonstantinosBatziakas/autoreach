# Building AutoReach Desktop (.exe)

## Prerequisites
```
pip install customtkinter pyinstaller groq requests beautifulsoup4 python-dotenv
```

## Build
```
cd C:\autoreach
desktop\build.bat
```
Output: `dist\AutoReach.exe` — double-click to run, no Python needed.

## First run
The app will ask for API keys in the Settings tab on first launch.
Config is saved to `%USERPROFILE%\.autoreach\autoreach.db`.

## Notes
- No browser, no terminal, no localhost — pure native window
- SQLite database lives in the user's home folder
- All data stays local except actual API calls
