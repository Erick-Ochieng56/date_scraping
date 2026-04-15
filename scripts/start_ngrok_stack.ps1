# Build Vite, run Django :8000, start ngrok. From repo root (not backend/):
#   powershell -ExecutionPolicy Bypass -File scripts/start_ngrok_stack.ps1
# In Git Bash, use the shell script instead (bash cannot run .ps1):
#   bash scripts/start_ngrok_stack.sh
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$VenvPy = Join-Path $Root "source\venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    $VenvPy = "python"
}

Set-Location (Join-Path $Root "frontend")
& npm run build

Set-Location (Join-Path $Root "backend")
if (-not $env:DJANGO_SERVE_SPA) { $env:DJANGO_SERVE_SPA = "1" }
if (-not $env:DJANGO_DISABLE_CORS) { $env:DJANGO_DISABLE_CORS = "1" }
if (-not $env:DJANGO_DEBUG) { $env:DJANGO_DEBUG = "1" }
if (-not $env:DJANGO_USE_X_FORWARDED_HOST) { $env:DJANGO_USE_X_FORWARDED_HOST = "1" }
if (-not $env:DJANGO_BEHIND_HTTPS_PROXY) { $env:DJANGO_BEHIND_HTTPS_PROXY = "1" }

Write-Host "Starting Django on http://127.0.0.1:8000 ..."
$django = Start-Process -FilePath $VenvPy -ArgumentList "manage.py", "runserver", "8000" -PassThru -NoNewWindow

Start-Sleep -Seconds 2
Write-Host "Starting ngrok..."
$ngrok = Start-Process -FilePath "ngrok" -ArgumentList "http", "8000" -PassThru -NoNewWindow

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "=== Public ngrok URL(s) ==="
try {
    $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -Method Get
    foreach ($t in $tunnels.tunnels) {
        if ($t.public_url) { Write-Host $t.public_url }
    }
} catch {
    Write-Host "(Open http://127.0.0.1:4040 in a browser for the public URL.)"
}
Write-Host ""
Write-Host "If CSRF fails on POST, set DJANGO_CSRF_TRUSTED_ORIGINS to your full https origin (e.g. .ngrok-free.dev or .ngrok-free.app)."
Write-Host "Press Enter to stop Django and ngrok..."
$null = Read-Host

Stop-Process -Id $ngrok.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $django.Id -Force -ErrorAction SilentlyContinue
