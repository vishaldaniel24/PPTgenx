@echo off
REM =============================================================================
REM NeuraDeck 1-Click Setup (Windows)
REM Creates venv, installs all deps, then starts backend + frontend
REM =============================================================================
cd /d "%~dp0"

echo.
echo [1/4] Checking Python...
python --version 2>nul || (
  echo ERROR: Python not found. Install Python 3.10+ from https://python.org
  pause
  exit /b 1
)

echo.
echo [2/4] Creating virtual environment...
if not exist .venv (
  python -m venv .venv
  echo Created .venv
) else (
  echo .venv already exists
)

echo.
echo [3/4] Installing dependencies (this may take a minute)...
call .venv\Scripts\activate.bat
pip install --upgrade pip -q
pip install -r requirements.txt -q
if errorlevel 1 (
  echo ERROR: pip install failed. Try: .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
echo Dependencies OK.

echo.
echo [4/4] Starting NeuraDeck...
echo   Backend:  http://localhost:8000  (docs: http://localhost:8000/docs)
echo   Frontend: http://localhost:8501
echo.

REM Start backend in new window (must run from backend dir so "app" package resolves)
start "NeuraDeck Backend" cmd /k "cd /d "%~dp0backend" && "%~dp0.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000"

REM Wait for backend to bind
timeout /t 3 /nobreak >nul

REM Start frontend in new window
start "NeuraDeck Frontend" cmd /k "cd /d "%~dp0frontend" && "%~dp0.venv\Scripts\streamlit.exe" run app.py --server.headless true"

echo.
echo Setup complete. Two windows opened:
echo   - Backend (FastAPI) on port 8000
echo   - Frontend (Streamlit) on port 8501
echo.
echo Open in browser: http://localhost:8501
echo Try prompt: "Tesla FSD v13" then Download PPTX.
echo.
pause
