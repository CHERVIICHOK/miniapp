param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $config = Invoke-RestMethod "http://127.0.0.1:$Port/api/config"
    if ($config.mode -ne 'telegram') { throw 'Start the app with .\start.ps1 -Mode telegram before exposing a tunnel.' }
    $tool = Join-Path $PSScriptRoot '.tools\cloudflared.exe'
    if (-not (Test-Path -LiteralPath $tool)) { throw 'Download official cloudflared-windows-amd64.exe to .tools\cloudflared.exe. See README.md.' }
    $checksumFile = Join-Path $PSScriptRoot '.tools\cloudflared.sha256'
    if (-not (Test-Path -LiteralPath $checksumFile)) { throw 'Run python -m scripts.install_cloudflared to verify the tunnel client.' }
    $expected = (Get-Content -LiteralPath $checksumFile -Raw).Trim()
    if ((Get-FileHash -LiteralPath $tool -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'cloudflared checksum mismatch. Reinstall with scripts.install_cloudflared.' }
    Write-Host 'Copy the https://*.trycloudflare.com URL to the configure_telegram command. Keep this terminal open.'
    & $tool tunnel --url "http://127.0.0.1:$Port" --no-autoupdate
} finally { Pop-Location }
