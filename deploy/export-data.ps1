[CmdletBinding()]
param([string]$Output = 'D:\CreatorLab\builtwhys-server-data.tar.gz')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) { throw 'tar.exe is required.' }
Push-Location $root
try {
    & tar.exe -czf $Output storage automation/pilots
    if ($LASTEXITCODE -ne 0) { throw "tar failed with exit code $LASTEXITCODE" }
} finally { Pop-Location }
Write-Host "Server data package created: $Output"
