@echo off
title NeuraDeck - Virtual Env Auto-Start
color 0A

echo 🚀 NeuraDeck Virtual Environment Startup...
cd /d "D:\Dani\ppt project"

REM Create venv if missing
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Backend Terminal (venv)
start cmd /k "cd /d D:\Dani\ppt project && call venv\Scripts\activate && cd backend && color 0B && echo ✅ Backend && python -m uvicorn main:app --port 8000 --reload"

REM Frontend Terminal (venv)  
start cmd /k "cd /d D:\Dani\ppt project && call venv\Scripts\activate && color 0A && echo ✅ Frontend && streamlit run app.py --server.port 8501 --server.headless true"

timeout /t 7 >nul
start http://localhost:8501

echo 🎉 NeuraDeck Ready! 2 terminals + browser open.
pause
