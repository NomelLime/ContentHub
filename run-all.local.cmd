@echo off
setlocal

REM ------------------------------------------------------------------
REM Local one-click launcher for your machine.
REM Fill CH_TUNNEL_PASSWORD below (or set it in system env vars).
REM ------------------------------------------------------------------

set "CH_TUNNEL_TOOL=plink"
set "CH_TUNNEL_HOST=199.192.22.121"
set "CH_TUNNEL_USER=root"
set "CH_TUNNEL_PASSWORD=As03Q6JelKJVjSOsPGdari7PCxtEt92y44nm"

REM Optional:
set "CH_FRONTEND_PORT=4173"
set "CH_BACKEND_PORT=8000"
set "CH_SKIP_BUILD=0"
set "CH_NO_TUNNEL=0"

if "%CH_TUNNEL_PASSWORD%"=="" (
  echo [WARN] CH_TUNNEL_PASSWORD is empty.
  echo        Set it in this file or as a system environment variable.
)

call "%~dp0run-all.cmd"
set "EXIT_CODE=%ERRORLEVEL%"

endlocal
exit /b %EXIT_CODE%
