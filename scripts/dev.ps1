<#
Start the Sentinel V4 console for development (Windows).
  scripts\dev.ps1          API on :8000 + console on :5173
  scripts\dev.ps1 -Mock    console only on :5173, answered by the in-browser mock (VITE_API_MOCK=1)
#>
param([switch]$Mock)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js >= 20 is required (https://nodejs.org)."
}
$major = [int](node -p "process.versions.node.split('.')[0]")
if ($major -lt 20) { throw "Node.js >= 20 is required; found $(node -v)." }

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not $Mock -and -not (Test-Path $py)) {
    throw "No .venv found. Create it: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt -r requirements-api.txt"
}
if (-not (Test-Path (Join-Path $root "web\node_modules"))) {
    Push-Location web; npm ci; Pop-Location
}

if ($Mock) {
    Write-Host "Console (mock API): http://127.0.0.1:5173"
    $env:VITE_API_MOCK = "1"
    Push-Location web
    try { npm run dev } finally { Pop-Location }
    return
}

$api = Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "src.api.app:create_app", "--factory", "--port", "8000", "--reload" -PassThru -NoNewWindow
Write-Host "API:     http://127.0.0.1:8000"
Write-Host "Console: http://127.0.0.1:5173"
try {
    Push-Location web
    npm run dev
} finally {
    Pop-Location
    if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force }
}
