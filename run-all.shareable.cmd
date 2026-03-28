@echo off
setlocal

REM ------------------------------------------------------------------
REM Shareable launcher template (safe to keep in git).
REM Copy to your own local file or edit values directly.
REM ------------------------------------------------------------------

set "CH_TUNNEL_TOOL=plink"
set "CH_TUNNEL_HOST=199.192.22.121"
set "CH_TUNNEL_USER=root"
set "CH_TUNNEL_PASSWORD=AAF1UPPC4zK0QOBcol1UViQEIfZcJaKz7p4"

set "CH_FRONTEND_PORT=4173"
set "CH_BACKEND_PORT=8000"
set "CH_SKIP_BUILD=0"
set "CH_NO_TUNNEL=0"

if "%CH_TUNNEL_PASSWORD%"=="PUT_PASSWORD_HERE" (
  echo [WARN] Set CH_TUNNEL_PASSWORD before first run.
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
