$ErrorActionPreference = 'Stop'
$Version = '1.14.2'
$Url = "https://github.com/SagerNet/sing-box/releases/download/v$Version/sing-box-$Version-windows-amd64.zip"
$Expected = 'c2d8bfff918755808781dfdeeb8581b6c91eb3a243d9a7b55483cfc0c0684d32'
$Root = Split-Path -Parent $PSScriptRoot
$Out = Join-Path $Root 'runtime'
$Zip = Join-Path $env:TEMP "sing-box-$Version-windows-amd64.zip"
Invoke-WebRequest -Uri $Url -OutFile $Zip
$Hash = (Get-FileHash -Algorithm SHA256 $Zip).Hash.ToLower()
if ($Hash -ne $Expected) { throw "SHA256 mismatch: $Hash" }
Expand-Archive -Path $Zip -DestinationPath $Out -Force
Write-Host "Installed verified sing-box $Version under $Out"
