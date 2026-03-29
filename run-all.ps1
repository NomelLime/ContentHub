param(
  [switch]$SkipBuild,
  [switch]$NoTunnel,
  [int]$FrontendPort = 4173,
  [int]$BackendPort = 8000,
  [string]$TunnelTarget = "",
  [string]$TunnelTool = "",
  [string]$TunnelHost = "",
  [string]$TunnelUser = "",
  [string]$TunnelPassword = "",
  [int]$TunnelLocalPort = 9090,
  [string]$TunnelRemoteHost = "127.0.0.1",
  [int]$TunnelRemotePort = 9090
)

$ErrorActionPreference = "Stop"

$monoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $monoRoot "_monorepo_env.ps1")
Import-MonorepoStackEnv -Root $monoRoot
$tunnelResolved = Resolve-TunnelParamsFromEnv -TunnelTarget $TunnelTarget -TunnelTool $TunnelTool `
  -TunnelHost $TunnelHost -TunnelUser $TunnelUser -TunnelPassword $TunnelPassword
$TunnelTarget = $tunnelResolved.TunnelTarget
$TunnelTool = $tunnelResolved.TunnelTool
$TunnelHost = $tunnelResolved.TunnelHost
$TunnelUser = $tunnelResolved.TunnelUser
$TunnelPassword = $tunnelResolved.TunnelPassword

function Stop-IfRunning {
  param([System.Diagnostics.Process]$Proc)
  if ($null -ne $Proc -and -not $Proc.HasExited) {
    try { Stop-Process -Id $Proc.Id -Force -ErrorAction Stop } catch {}
  }
}

function Test-HttpOk {
  param(
    [string]$Url,
    [int]$Attempts = 8,
    [int]$DelayMs = 1000
  )
  for ($i = 0; $i -lt $Attempts; $i++) {
    try {
      $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
        return $true
      }
    } catch {}
    Start-Sleep -Milliseconds $DelayMs
  }
  return $false
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

  if (-not $NoTunnel) {
    if ($TunnelTool -eq "plink") {
      if ([string]::IsNullOrWhiteSpace($TunnelHost) -or [string]::IsNullOrWhiteSpace($TunnelUser)) {
        throw "CH_TUNNEL_TOOL=plink requires CH_TUNNEL_HOST and CH_TUNNEL_USER"
      }
      Write-Host "==> Starting PLINK tunnel: localhost:$TunnelLocalPort -> $TunnelRemoteHost`:$TunnelRemotePort via $TunnelUser@$TunnelHost"
      $plinkArgs = @(
        "-batch",
        "-N",
        "-L", "$TunnelLocalPort`:$TunnelRemoteHost`:$TunnelRemotePort"
      )
      if (-not [string]::IsNullOrWhiteSpace($TunnelPassword)) {
        $plinkArgs += @("-pw", $TunnelPassword)
      }
      $plinkArgs += "$TunnelUser@$TunnelHost"
      $tunnelProc = Start-Process -FilePath "plink.exe" -ArgumentList $plinkArgs -PassThru `
        -NoNewWindow -WorkingDirectory $root -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr
    } elseif (-not [string]::IsNullOrWhiteSpace($TunnelTarget)) {
      Write-Host "==> Starting SSH tunnel: localhost:$TunnelLocalPort -> $TunnelRemoteHost`:$TunnelRemotePort via $TunnelTarget"
      $tunnelArgs = @(
        "-N",
        "-L", "$TunnelLocalPort`:$TunnelRemoteHost`:$TunnelRemotePort",
        $TunnelTarget
      )
      $tunnelProc = Start-Process -FilePath "ssh" -ArgumentList $tunnelArgs -PassThru `
        -NoNewWindow -WorkingDirectory $root -RedirectStandardOutput $tunnelOut -RedirectStandardError $tunnelErr
    } else {
      Write-Host "==> SSH tunnel skipped (set CH_TUNNEL_TARGET or CH_TUNNEL_TOOL=plink)"
    }
  } else {
    Write-Host "==> SSH tunnel skipped (flag -NoTunnel)"
  }

  Write-Host "==> Starting backend on :$BackendPort"
  $backendProc = Start-Process -FilePath "python" -ArgumentList @(
    "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$BackendPort", "--workers", "1"
  ) -PassThru -NoNewWindow -WorkingDirectory $backendDir -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr

  Write-Host "==> Starting frontend preview on :$FrontendPort"
  $frontendProc = Start-Process -FilePath "cmd.exe" -ArgumentList @(
    "/c", "npm run preview -- --host 0.0.0.0 --port $FrontendPort"
  ) -PassThru -NoNewWindow -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr

  Write-Host ""
  Write-Host "ContentHub started:"
  Write-Host "  Frontend: http://localhost:$FrontendPort"
  Write-Host "  Backend : http://localhost:$BackendPort"
  Write-Host "  Logs    : $runtimeDir"
  Write-Host ""
  Write-Host "Health checks:"
  $backendOk = Test-HttpOk -Url "http://localhost:$BackendPort/health"
  if ($backendOk) { Write-Host "  [OK] Backend /health" } else { Write-Host "  [FAIL] Backend /health (see $backendErr)" }
  $frontendOk = Test-HttpOk -Url "http://localhost:$FrontendPort"
  if ($frontendOk) { Write-Host "  [OK] Frontend root" } else { Write-Host "  [FAIL] Frontend root (see $frontendErr)" }
  if (-not $NoTunnel -and $null -ne $tunnelProc -and -not $tunnelProc.HasExited) {
    Start-Sleep -Milliseconds 800
    try {
      Invoke-RestMethod -Uri "http://127.0.0.1:$TunnelLocalPort/health" -TimeoutSec 8 -ErrorAction Stop | Out-Null
      Write-Host "  [OK] PreLend Internal API http://127.0.0.1:$TunnelLocalPort/health" -ForegroundColor Green
    } catch {
      Write-Host "  [WARN] PreLend Internal API на :$TunnelLocalPort не отвечает — задайте CH_TUNNEL_TARGET и проверьте VPS (systemctl status prelend-internal-api). Скрипт: scripts\verify-prelend-internal-api.ps1" -ForegroundColor Yellow
    }
  }
  Write-Host ""
  Write-Host "Press Ctrl+C to stop all processes."

  while ($true) {
    Start-Sleep -Seconds 2

    if ($backendProc.HasExited) { throw "Backend process exited. Check $backendErr" }
    if ($frontendProc.HasExited) { throw "Frontend process exited. Check $frontendErr" }
    if ($null -ne $tunnelProc -and $tunnelProc.HasExited) {
      $tail = ""
      if (Test-Path -LiteralPath $tunnelErr) {
        $tail = (Get-Content -LiteralPath $tunnelErr -Tail 8 -ErrorAction SilentlyContinue) -join "`n"
      }
      if ($tail) {
        throw "SSH tunnel process exited. Log $tunnelErr :`n$tail"
      }
      throw "SSH tunnel process exited. Check $tunnelErr"
    }
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
