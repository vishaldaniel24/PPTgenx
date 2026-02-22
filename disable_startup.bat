@echo off
REM =============================================================================
REM Remove NeuraDeck from Windows Startup.
REM =============================================================================
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set LINK=%STARTUP%\NeuraDeck Start Servers.lnk

if exist "%LINK%" (
  del "%LINK%"
  echo NeuraDeck removed from Windows Startup.
) else (
  echo No NeuraDeck startup shortcut found.
)
echo.
pause
