param([ValidateSet('local','telegram')][string]$Mode = 'local', [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv and install requirements.txt first. See README.md.' }
    $env:APP_MODE = $Mode
    Write-Host "MiniApp: http://127.0.0.1:$Port (mode: $Mode)"
    & $python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port $Port --no-proxy-headers
    if ($LASTEXITCODE -ne 0) { throw 'MiniApp server stopped with an error.' }
} finally { Pop-Location }
