@echo off
REM NEONEXUS - double-click to install and start on Windows 10/11
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" echo Install failed (exit code %RC%). See the messages above.
pause
exit /b %RC%
