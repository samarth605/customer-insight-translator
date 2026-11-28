@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
) else (
  echo Install Python and the requirements listed in README.md, then run this file again.
)
pause
