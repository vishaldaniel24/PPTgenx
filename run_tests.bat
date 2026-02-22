@echo off
REM 1-click test everything (from project root)
call "%~dp0tests\run_tests.bat"
exit /b %ERRORLEVEL%
