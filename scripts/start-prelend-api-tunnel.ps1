<#
.SYNOPSIS
  SSH port-forward: локальный порт -> PreLend Internal API на VPS (127.0.0.1:9090).

.DESCRIPTION
  На сервере uvicorn слушает только 127.0.0.1:9090. Снаружи доступ — через этот туннель.
  После запуска проверьте: .\verify-prelend-internal-api.ps1

  Переменные (или параметры):
    CH_TUNNEL_TARGET  — как для ssh: user@vps.example.com  (рекомендуется)
    CH_SSH_IDENTITY   — опционально: путь к приватному ключу (-i)

  PuTTY plink:
    $env:CH_TUNNEL_TOOL = "plink"
    $env:CH_TUNNEL_HOST = "vps.example.com"
    $env:CH_TUNNEL_USER = "deploy"

.EXAMPLE
  $env:CH_TUNNEL_TARGET = "ubuntu@203.0.113.10"
  .\start-prelend-api-tunnel.ps1

.EXAMPLE
  .\start-prelend-api-tunnel.ps1 -Target "ubuntu@203.0.113.10" -LocalPort 9090
#>
param(
  [string]$Target = $env:CH_TUNNEL_TARGET,
  [string]$Identity = $env:CH_SSH_IDENTITY,
  [int]$LocalPort = 9090,
  [string]$RemoteHost = "127.0.0.1",
  [int]$RemotePort = 9090
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Target)) {
  Write-Host @"
Не задан целевой SSH-хост.

Задайте один из вариантов:
  `$env:CH_TUNNEL_TARGET = 'user@ваш-vps-ip'
  .\start-prelend-api-tunnel.ps1 -Target 'user@ваш-vps-ip'

Опционально ключ:
  `$env:CH_SSH_IDENTITY = '$HOME\.ssh\id_ed25519'
"@ -ForegroundColor Yellow
  exit 1
}

$bind = "${LocalPort}:${RemoteHost}:${RemotePort}"
Write-Host "Туннель: localhost:$LocalPort -> ${RemoteHost}:$RemotePort на $Target" -ForegroundColor Cyan
Write-Host "Оставьте окно открытым. Остановка: Ctrl+C" -ForegroundColor Gray

$sshArgs = @("-N", "-L", $bind)
if (-not [string]::IsNullOrWhiteSpace($Identity)) {
  $sshArgs = @("-i", $Identity) + $sshArgs
}
$sshArgs += $Target

& ssh @sshArgs
