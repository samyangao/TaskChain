@echo off
rem Starts TaskChain. Creates the virtual environment on first run.
cd /d "%~dp0\.."
if not exist "venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv venv
)
call "venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
python run.py
