[CmdletBinding()]
param(
    [string]$PageName = 'BuiltWhys',
    [string]$PageId = '1172665885939816',
    [string]$GraphVersion = 'v25.0'
)

$ErrorActionPreference = 'Stop'
$secretDirectory = Join-Path $env:LOCALAPPDATA 'BuiltWhys'
$secretPath = Join-Path $secretDirectory 'meta.secrets.clixml'

Write-Output 'Meta anahtarlarini bu pencerede girin. Degerler ekrana veya proje dosyalarina yazilmaz.'
$appId = (Read-Host 'Meta App ID').Trim()
$appSecretSecure = Read-Host 'Meta App Secret' -AsSecureString
$userTokenSecure = Read-Host 'Graph API Explorer User Access Token' -AsSecureString

if ([string]::IsNullOrWhiteSpace($appId)) { throw 'Meta App ID is required.' }

function ConvertTo-PlainText([Security.SecureString]$Value) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}

$appSecret = ConvertTo-PlainText $appSecretSecure
$shortUserToken = ConvertTo-PlainText $userTokenSecure
try {
    $exchange = Invoke-RestMethod -Method Post `
        -Uri "https://graph.facebook.com/$GraphVersion/oauth/access_token" `
        -Body @{
            grant_type = 'fb_exchange_token'
            client_id = $appId
            client_secret = $appSecret
            fb_exchange_token = $shortUserToken
        }
    $longUserToken = [string]$exchange.access_token
    if ([string]::IsNullOrWhiteSpace($longUserToken)) { throw 'Meta did not return a long-lived user token.' }

    $headers = @{ Authorization = "Bearer $longUserToken" }
    $accounts = Invoke-RestMethod -Method Get `
        -Uri "https://graph.facebook.com/$GraphVersion/me/accounts?fields=id,name,access_token,instagram_business_account%7Bid,username%7D&limit=100" `
        -Headers $headers
    $page = @($accounts.data) | Where-Object { $_.name -eq $PageName } | Select-Object -First 1
    if ($null -eq $page) {
        try {
            $page = Invoke-RestMethod -Method Get `
                -Uri "https://graph.facebook.com/$GraphVersion/$PageId`?fields=id,name,access_token,instagram_business_account%7Bid,username%7D" `
                -Headers $headers
        } catch {
            $permissionResponse = Invoke-RestMethod -Method Get `
                -Uri "https://graph.facebook.com/$GraphVersion/me/permissions" `
                -Headers $headers
            $granted = (@($permissionResponse.data) | Where-Object { $_.status -eq 'granted' } | ForEach-Object { $_.permission }) -join ', '
            $declined = (@($permissionResponse.data) | Where-Object { $_.status -ne 'granted' } | ForEach-Object { $_.permission }) -join ', '
            throw "BuiltWhys Page access is missing. Granted permissions: $granted. Declined or expired permissions: $declined"
        }
    }
    if ([string]::IsNullOrWhiteSpace([string]$page.access_token)) {
        throw "BuiltWhys Page was found, but Meta did not return a Page Access Token. Reauthorize the app with BuiltWhys Page access."
    }
    if ($null -eq $page.instagram_business_account) {
        throw "Facebook Page '$PageName' has no Instagram professional account in the API response."
    }

    New-Item -ItemType Directory -Path $secretDirectory -Force | Out-Null
    [pscustomobject]@{
        AppId = $appId
        AppSecret = ConvertTo-SecureString $appSecret -AsPlainText -Force
        UserAccessToken = ConvertTo-SecureString $longUserToken -AsPlainText -Force
        PageAccessToken = ConvertTo-SecureString ([string]$page.access_token) -AsPlainText -Force
        PageId = [string]$page.id
        PageName = [string]$page.name
        InstagramUserId = [string]$page.instagram_business_account.id
        InstagramUsername = [string]$page.instagram_business_account.username
        GraphVersion = $GraphVersion
        CreatedAt = (Get-Date).ToUniversalTime().ToString('o')
    } | Export-Clixml -LiteralPath $secretPath

    Write-Output "Connected Facebook Page: $($page.name)"
    Write-Output "Connected Instagram: @$($page.instagram_business_account.username)"
    Write-Output "Meta settings were encrypted for the current Windows user: $secretPath"
} finally {
    $appSecret = $null
    $shortUserToken = $null
    $longUserToken = $null
}
