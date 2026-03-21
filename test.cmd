@echo off
setlocal

REM Local launcher (double-click friendly)
set "CH_TUNNEL_TOOL=plink"
set "CH_TUNNEL_HOST=199.192.22.121"
set "CH_TUNNEL_USER=root"
set "CH_TUNNEL_PASSWORD="

set "CH_FRONTEND_PORT=4173"
set "CH_BACKEND_PORT=8000"
set "CH_SKIP_BUILD=0"
set "CH_NO_TUNNEL=0"

if "%CH_TUNNEL_PASSWORD%"=="" (
  echo [WARN] CH_TUNNEL_PASSWORD is empty.
  echo        Fill it in this file or set system env var.
)

call "%~dp0run-all.cmd"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
  echo [INFO] Launcher finished without errors.
) else (
  echo [ERROR] Launcher exited with code %EXIT_CODE%.
)
echo [INFO] Frontend: http://localhost:%CH_FRONTEND_PORT%
echo [INFO] Backend : http://localhost:%CH_BACKEND_PORT%/health
echo [INFO] Logs    : "%~dp0.runtime"
echo.
pause

endlocal
exit /b %EXIT_CODE%
