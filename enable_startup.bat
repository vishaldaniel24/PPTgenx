@echo off
REM =============================================================================
REM Add NeuraDeck to Windows Startup — servers will start when you log in.
REM Run this once. To remove, run disable_startup.bat
REM =============================================================================
cd /d "%~dp0"

set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set LINK=%STARTUP%\NeuraDeck Start Servers.lnk

echo Adding NeuraDeck to Windows Startup...
echo Startup folder: %STARTUP%
echo.

REM Create shortcut using PowerShell (works on all Windows 10/11)
powershell -NoProfile -Command ^
  "$WshShell = New-Object -ComObject WScript.Shell; ^
   $Shortcut = $WshShell.CreateShortcut('%LINK%'); ^
   $Shortcut.TargetPath = '%~dp0start_all_servers.bat'; ^
   $Shortcut.WorkingDirectory = '%~dp0'; ^
   $Shortcut.WindowStyle = 7; ^
   $Shortcut.Description = 'Start NeuraDeck backend, frontend and website'; ^
   $Shortcut.Save()"

if exist "%LINK%" (
  echo ✅ Done! NeuraDeck will start automatically when you log in.
  echo 🌐 Website: http://localhost:8501
  echo ⏹️  To disable: run disable_startup.bat
) else (
  echo ❌ Failed. Create manually:
  echo   Right-click start_all_servers.bat → Send to → Desktop (create shortcut)
  echo   Move shortcut to: %STARTUP%
)
echo.
pause
