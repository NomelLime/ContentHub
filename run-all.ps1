param(
  [switch]$SkipBuild,
  [switch]$NoTunnel,
  [int]$FrontendPort = 4173,
  [int]$BackendPort = 8000,
  [string]$TunnelTarget = $env:CH_TUNNEL_TARGET,
  [int]$TunnelLocalPort = 9090,
  [string]$TunnelRemoteHost = "127.0.0.1",
  [int]$TunnelRemotePort = 9090
)

$ErrorActionPreference = "Stop"

function Stop-IfRunning {
  param([System.Diagnostics.Process]$Proc)
  if ($null -ne $Proc -and -not $Proc.HasExited) {
    try { Stop-Process -Id $Proc.Id -Force -ErrorAction Stop } catch {}
  }
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendDir = Join-Path $root "frontend"
$backendDir = Join-Path $root "backend"
$runtimeDir = Join-Path $root ".runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$backendOut = Join-Path $runtimeDir "backend.out.log"
$backendErr = Join-Path $runtimeDir "backend.err.log"
$frontendOut = Join-Path $runtimeDir "frontend.out.log"
$frontendErr = Join-Path $runtimeDir "frontend.err.log"
$tunnelOut = Join-Path $runtimeDir "tunnel.out.log"
$tunnelErr = Join-Path $runtimeDir "tunnel.err.log"

$backendProc = $null
$frontendProc = $null
$tunnelProc = $null

try {
  if (-not $SkipBuild) {
    Write-Host "==> Frontend build..."
    Push-Location $frontendDir
    try {
      & cmd /c "npm run build"
    } finally {
      Pop-Location
    }
  } else {
    Write-Host "==> Skip frontend build (flag -SkipBuild)"
  }

  if (-not $NoTunnel -and -not [string]::IsNullOrWhiteSpace($TunnelTarget)) {
    Write-Host "==> Starting SSH tunnel: localhost:$TunnelLocalPort -> $TunnelRemoteHost`:$TunnelRemotePort via $TunnelTarget"
    $tunnelArgs = @(
      "-N",
      "-L", "$TunnelLocalPort`:$TunnelRemoteHost`:$TunnelRemotePort",
      $TunnelTarget
    )
    $tunnelProc = Start-Process -FilePath "ssh" -ArgumentList $tunnelArgs -PassThru `
      -WorkingDirectory $root -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr
  } else {
    Write-Host "==> SSH tunnel skipped (use -NoTunnel or set CH_TUNNEL_TARGET)"
  }

  Write-Host "==> Starting backend on :$BackendPort"
  $backendProc = Start-Process -FilePath "python" -ArgumentList @(
    "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$BackendPort", "--workers", "1"
  ) -PassThru -WorkingDirectory $backendDir -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr

  Write-Host "==> Starting frontend preview on :$FrontendPort"
  $frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
    "/c", "npm run preview -- --host 0.0.0.0 --port $FrontendPort"
  ) -PassThru -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr

  Write-Host ""
  Write-Host "ContentHub started:"
  Write-Host "  Frontend: http://localhost:$FrontendPort"
  Write-Host "  Backend : http://localhost:$BackendPort"
  Write-Host "  Logs    : $runtimeDir"
  Write-Host ""
  Write-Host "Press Ctrl+C to stop all processes."

  while ($true) {
    Start-Sleep -Seconds 2

    if ($backendProc.HasExited) { throw "Backend process exited. Check $backendErr" }
    if ($frontendProc.HasExited) { throw "Frontend process exited. Check $frontendErr" }
    if ($null -ne $tunnelProc -and $tunnelProc.HasExited) { throw "SSH tunnel process exited. Check $tunnelErr" }
  }
}
finally {
  Write-Host ""
  Write-Host "==> Stopping processes..."
  Stop-IfRunning -Proc $frontendProc
  Stop-IfRunning -Proc $backendProc
  Stop-IfRunning -Proc $tunnelProc
  Write-Host "==> Stopped."
}
