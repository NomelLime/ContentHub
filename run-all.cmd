@echo off
setlocal EnableExtensions

REM -----------------------------------------------------------------------------
REM ContentHub one-click launcher (Windows CMD wrapper)
REM -----------------------------------------------------------------------------
REM Optional environment variables:
REM   CH_SKIP_BUILD=1
REM   CH_NO_TUNNEL=1
REM   CH_FRONTEND_PORT=4173
REM   CH_BACKEND_PORT=8000
REM   CH_TUNNEL_TARGET=user@host
REM
REM For plink mode (like your old script):
REM   CH_TUNNEL_TOOL=plink
REM   CH_TUNNEL_HOST=199.192.22.121
REM   CH_TUNNEL_USER=root
REM   CH_TUNNEL_PASSWORD=your_password
REM -----------------------------------------------------------------------------

set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%run-all.ps1"

if not exist "%PS1%" (
  echo [ERROR] File not found: "%PS1%"
  exit /b 1
)

set "PS_ARGS=-ExecutionPolicy Bypass -File "%PS1%""

if "%CH_SKIP_BUILD%"=="1" set "PS_ARGS=%PS_ARGS% -SkipBuild"
if "%CH_NO_TUNNEL%"=="1"  set "PS_ARGS=%PS_ARGS% -NoTunnel"
if not "%CH_FRONTEND_PORT%"=="" set "PS_ARGS=%PS_ARGS% -FrontendPort %CH_FRONTEND_PORT%"
if not "%CH_BACKEND_PORT%"==""  set "PS_ARGS=%PS_ARGS% -BackendPort %CH_BACKEND_PORT%"

REM If explicitly provided, pass normal SSH target to PowerShell script
if not "%CH_TUNNEL_TARGET%"=="" set "PS_ARGS=%PS_ARGS% -TunnelTarget "%CH_TUNNEL_TARGET%""

REM -----------------------------------------------------------------
REM Optional plink pre-tunnel mode:
REM Starts separate plink process and then runs PowerShell launcher
REM with -NoTunnel (to avoid duplicate tunnel from ssh).
REM -----------------------------------------------------------------
if /I "%CH_TUNNEL_TOOL%"=="plink" (
  if "%CH_NO_TUNNEL%"=="1" goto run_ps

  if "%CH_TUNNEL_HOST%"=="" (
    echo [ERROR] CH_TUNNEL_HOST is required for plink mode.
    exit /b 1
  )
  if "%CH_TUNNEL_USER%"=="" (
    echo [ERROR] CH_TUNNEL_USER is required for plink mode.
    exit /b 1
  )

  set "PLINK_CMD=plink.exe -batch -N -L 9090:127.0.0.1:9090 %CH_TUNNEL_USER%@%CH_TUNNEL_HOST%"
  if not "%CH_TUNNEL_PASSWORD%"=="" (
    set "PLINK_CMD=plink.exe -batch -pw "%CH_TUNNEL_PASSWORD%" -N -L 9090:127.0.0.1:9090 %CH_TUNNEL_USER%@%CH_TUNNEL_HOST%"
  )

  echo [INFO] Starting plink tunnel...
  start "ContentHub SSH Tunnel" cmd /c "%PLINK_CMD%"
  set "PS_ARGS=%PS_ARGS% -NoTunnel"
)

:run_ps
echo [INFO] Starting ContentHub...
powershell %PS_ARGS%
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo [ERROR] ContentHub stopped with code %EXIT_CODE%
  exit /b %EXIT_CODE%
)

endlocal
exit /b 0
