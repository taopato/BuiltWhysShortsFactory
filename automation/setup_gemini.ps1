[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$secretDirectory = Join-Path $env:LOCALAPPDATA 'BuiltWhys'
$secretPath = Join-Path $secretDirectory 'gemini.secrets.clixml'

Write-Host 'The key stays on this PC and is encrypted for the current Windows user.'
$apiKey = Read-Host 'Gemini API key' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $models = Invoke-RestMethod -Method Get -Uri "https://generativelanguage.googleapis.com/v1beta/models?key=$plainKey"
    $imageModel = @($models.models | Where-Object { $_.name -eq 'models/gemini-2.5-flash-image' })
    if ($imageModel.Count -eq 0) {
        throw 'The key works, but gemini-2.5-flash-image is not available to this API project. Check that Gemini API billing is enabled.'
    }
} finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $plainKey = $null
}

New-Item -ItemType Directory -Force -Path $secretDirectory | Out-Null
[PSCustomObject]@{
    ApiKey = $apiKey
    Model = 'gemini-2.5-flash-image'
} | Export-Clixml -LiteralPath $secretPath

Write-Host "Gemini connected. Settings encrypted for this Windows user: $secretPath"

