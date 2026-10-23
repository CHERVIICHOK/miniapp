param([ValidateSet('local','telegram')][string]$Mode = 'local', [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv and install requirements.txt first. See README.md.' }
    $pythonPlatform = & $python -c 'import sysconfig; print(sysconfig.get_platform())'
    if ($LASTEXITCODE -ne 0 -or $pythonPlatform.Trim() -ne 'win-amd64') { throw 'Use Windows CPython x64, not MSYS2/MinGW. Recreate .venv with py -3.12 -m venv .venv. See README.md.' }
    $env:APP_MODE = $Mode
    Write-Host "MiniApp: http://127.0.0.1:$Port (mode: $Mode)"
    & $python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port $Port --no-proxy-headers
    if ($LASTEXITCODE -ne 0) { throw 'MiniApp server stopped with an error.' }
} finally { Pop-Location }
