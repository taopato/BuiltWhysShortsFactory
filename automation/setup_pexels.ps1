[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$secretDirectory = Join-Path $env:LOCALAPPDATA 'BuiltWhys'
$secretPath = Join-Path $secretDirectory 'pexels.secrets.clixml'

Write-Host 'The Pexels key stays on this PC and is encrypted for the current Windows user.'
$apiKey = Read-Host 'Pexels API key' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $headers = @{ Authorization = $plainKey }
    $null = Invoke-RestMethod -Method Get -Headers $headers -Uri 'https://api.pexels.com/v1/collections?per_page=1'
} finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $plainKey = $null
}

New-Item -ItemType Directory -Force -Path $secretDirectory | Out-Null
[PSCustomObject]@{ ApiKey = $apiKey } | Export-Clixml -LiteralPath $secretPath
Write-Host "Pexels connected. Settings encrypted for this Windows user: $secretPath"

