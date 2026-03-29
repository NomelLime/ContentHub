<#
.SYNOPSIS
  Проверка доступа к PreLend Internal API (туннель localhost:9090 + ключ).

.DESCRIPTION
  Читает PL_INTERNAL_API_URL и PL_INTERNAL_API_KEY из окружения.
  У ContentHub они подхватываются из GitHub/.secrets.env и backend/.env при старте uvicorn.

  1) GET /health — без ключа
  2) GET /config/advertisers — с X-API-Key (как Orchestrator/ContentHub)

  Ключ на локали и на VPS (systemd EnvironmentFile=/run/prelend.env или Environment=) должен совпадать.
#>
$ErrorActionPreference = "Continue"

function Import-DotEnvFile {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { return }
  Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $eq = $line.IndexOf("=")
    if ($eq -lt 1) { return }
    $k = $line.Substring(0, $eq).Trim()
    $v = $line.Substring($eq + 1).Trim()
    if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
      $v = $v.Substring(1, $v.Length - 2)
    }
    if ($k) { Set-Item -Path "env:$k" -Value $v }
  }
}

# Подхват PL_* как у uvicorn (main.py грузит .secrets.env → backend/.env)
$monoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Import-DotEnvFile (Join-Path $monoRoot ".secrets.env")
Import-DotEnvFile (Join-Path $monoRoot "ContentHub\backend\.env")

$base = ($env:PL_INTERNAL_API_URL).TrimEnd("/")
if ([string]::IsNullOrWhiteSpace($base)) { $base = "http://127.0.0.1:9090" }

$key = ($env:PL_INTERNAL_API_KEY).Trim()
$healthUrl = "$base/health"
$cfgUrl = "$base/config/advertisers"

Write-Host "URL: $base" -ForegroundColor Cyan

try {
  $h = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 8
  Write-Host "[OK] GET /health" -ForegroundColor Green
  $h | ConvertTo-Json -Compress -Depth 4 | Write-Host
} catch {
  Write-Host "[FAIL] GET /health — туннель не поднят или API на VPS не слушает 127.0.0.1:9090" -ForegroundColor Red
  Write-Host $_.Exception.Message
  Write-Host @"

Действия:
  1) На VPS: sudo systemctl status prelend-internal-api
  2) Локально: .\scripts\start-prelend-api-tunnel.ps1 (с CH_TUNNEL_TARGET=user@vps)
"@ -ForegroundColor Yellow
  exit 1
}

if ([string]::IsNullOrWhiteSpace($key)) {
  Write-Host "[WARN] PL_INTERNAL_API_KEY пуст — проверка /config/advertisers пропущена." -ForegroundColor Yellow
  Write-Host "Задайте тот же ключ, что в окружении prelend-internal-api на VPS (GitHub/.secrets.env или backend/.env)."
  exit 0
}

try {
  $headers = @{ "X-API-Key" = $key }
  $adv = Invoke-RestMethod -Uri $cfgUrl -Method Get -Headers $headers -TimeoutSec 15
  $n = @($adv).Count
  Write-Host "[OK] GET /config/advertisers (элементов: $n)" -ForegroundColor Green
} catch {
  Write-Host "[FAIL] GET /config/advertisers — неверный PL_INTERNAL_API_KEY или 403" -ForegroundColor Red
  Write-Host $_.Exception.Message
  Write-Host @"

Синхронизируйте ключ:
  Локально: GitHub/.secrets.env или ContentHub/backend/.env → PL_INTERNAL_API_KEY=...
  На VPS:   sudo grep PL_INTERNAL /run/prelend.env
            или sudo systemctl show prelend-internal-api -p Environment
  После смены ключа на VPS: sudo systemctl restart prelend-internal-api
"@ -ForegroundColor Yellow
  exit 1
}

Write-Host "`nГотово: ContentHub может использовать PL_INTERNAL_API_URL=$base" -ForegroundColor Green
