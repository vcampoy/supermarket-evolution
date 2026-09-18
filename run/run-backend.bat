@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "START_SCRIPT=%PROJECT_ROOT%\src\scripts\start-backend.ps1"

if not exist "%START_SCRIPT%" (
    echo [ERROR] Backend start script not found: "%START_SCRIPT%"
    exit /b 1
)

echo Starting Supermarket Evolution backend at http://127.0.0.1:8000
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%START_SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Backend stopped with exit code %EXIT_CODE%.
)

exit /b %EXIT_CODE%
