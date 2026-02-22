@echo off
REM Run Streamlit frontend from THIS project's frontend folder.
cd /d "%~dp0"
echo Starting NeuraDeck frontend from: %CD%
echo You should see "NeuraDeck Immersive UI" and "Generate PPT" button.
echo.
"%~dp0..\.venv\Scripts\streamlit.exe" run app.py --server.headless true
pause
