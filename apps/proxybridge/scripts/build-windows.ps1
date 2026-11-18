$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root 'dist'
New-Item -ItemType Directory -Force -Path $dist | Out-Null
go build -trimpath -ldflags "-s -w" -o (Join-Path $dist 'ProxyBridge.exe') (Join-Path $root 'cmd/proxybridge')
Copy-Item (Join-Path $root 'extension') $dist -Recurse -Force
Copy-Item (Join-Path $root 'configs') $dist -Recurse -Force
Write-Host "Built $dist\ProxyBridge.exe"
