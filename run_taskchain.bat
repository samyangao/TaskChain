@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Virtual environment not found. Create it with: python -m venv venv
  pause
  exit /b 1
)
call "venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
python app.py
