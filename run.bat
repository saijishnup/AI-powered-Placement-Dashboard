@echo off
rem One-click start: OmniRoute gateway (AI features) + the Streamlit app. Opens the browser.
cd /d "%~dp0"

if not exist .env (
  copy .env.example .env >nul
  echo Created .env from .env.example. Paste your OmniRoute API key into LLM_API_KEY, then run this again.
  notepad .env
  exit /b
)

netstat -ano | findstr "127.0.0.1:20128" | findstr LISTENING >nul
if errorlevel 1 (
  if exist "%APPDATA%\npm\omniroute.cmd" (
    set "OMNIROUTE_SERVER_HOST=127.0.0.1"
    start "OmniRoute" /min "%APPDATA%\npm\omniroute.cmd"
  ) else (
    echo OmniRoute not found: charts and tables work, AI answers will show as unavailable.
  )
)

if not exist .venv\Scripts\python.exe (
  echo First run: creating .venv and installing requirements...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install -q -r requirements.txt
)

.venv\Scripts\python -m streamlit run app.py
