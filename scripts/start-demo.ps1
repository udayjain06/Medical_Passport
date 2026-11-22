[CmdletBinding()]
param(
    [Parameter()]
    [ValidatePattern('^[a-zA-Z0-9.-]+$')]
    [string]$LanHost,
    [Parameter()]
    [ValidateRange(1024, 65535)]
    [int]$WebPort = 3000
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
$alembic = Join-Path $backend ".venv\Scripts\alembic.exe"
$uvicorn = Join-Path $backend ".venv\Scripts\uvicorn.exe"
$seed = Join-Path $root "scripts\seed_demo.py"
$demoExample = Join-Path $root ".env.demo.example"

foreach ($path in @($python, $alembic, $uvicorn, (Join-Path $frontend "node_modules"), $demoExample)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing local demo dependency or configuration: $path"
    }
}

function Get-EnvSetting([string]$Path, [string]$Name) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*?)\s*$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Get-ProjectListener([int]$Port) {
    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $connection) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
    if (-not $process) {
        throw "Port $Port is occupied but its process identity cannot be verified. Nothing was stopped."
    }
    return $process
}

function Stop-VerifiedBackend([int]$Port) {
    $process = Get-ProjectListener $Port
    if (-not $process) { return }
    $exe = [string]$process.ExecutablePath
    $cmd = [string]$process.CommandLine
    $venvPrefix = [regex]::Escape((Join-Path $backend ".venv\Scripts\"))
    $backendRoot = [regex]::Escape($backend)
    $verifiedCommand = $cmd -match "(?i)$backendRoot" -and
        $cmd -match "(?i)uvicorn" -and
        $cmd -match "app\.main:app" -and
        $cmd -match "(?i)--port\s+$Port\b"
    $verifiedExecutable = $exe -match "(?i)^$venvPrefix" -or (
        $exe -match "(?i)python\.exe$" -and $verifiedCommand
    )
    if (-not $verifiedExecutable -or -not $verifiedCommand) {
        throw "Port $Port is occupied by a process that is not verified as this project's backend. Nothing was stopped."
    }
    Stop-Process -Id $process.ProcessId
    $limit = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $limit -and (Get-ProjectListener $Port)) { Start-Sleep -Milliseconds 250 }
}

function Stop-VerifiedFrontend([int]$Port) {
    $process = Get-ProjectListener $Port
    if (-not $process) { return }
    $frontendRoot = [regex]::Escape($frontend)
    $listenerCommand = [string]$process.CommandLine
    $verifiedNextListener = $process.ExecutablePath -match "(?i)node\.exe$" -and
        $listenerCommand -match "(?i)$frontendRoot" -and
        $listenerCommand -match "(?i)next"
    $parentId = [int]$process.ParentProcessId
    $verifiedDevParent = $false
    for ($depth = 0; $depth -lt 5 -and $parentId -gt 0; $depth++) {
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $parentId" -ErrorAction SilentlyContinue
        if (-not $parent) { break }
        $parentCommand = [string]$parent.CommandLine
        if (
            $parent.ExecutablePath -match "(?i)node\.exe$" -and
            $parentCommand -match "(?i)$frontendRoot" -and
            $parentCommand -match "(?i)next" -and
            $parentCommand -match "(?i)\bdev\b"
        ) {
            $verifiedDevParent = $true
            break
        }
        $parentId = [int]$parent.ParentProcessId
    }
    if (-not $verifiedNextListener -or -not $verifiedDevParent) {
        throw "Port $Port is occupied by a process that is not verified as this project's Next.js dev server. Nothing was stopped."
    }
    Stop-Process -Id $process.ProcessId
    $limit = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $limit -and (Get-ProjectListener $Port)) { Start-Sleep -Milliseconds 250 }
}

function Test-Ready([string]$Url) {
    try {
        return (Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200
    } catch {
        return $false
    }
}

function Test-DemoEnabled([string]$Origin) {
    try {
        $response = Invoke-RestMethod -Uri "$Origin/api/auth/demo-status" -TimeoutSec 3
        return [bool]$response.enabled
    } catch {
        return $false
    }
}

function Invoke-BackendPython([string[]]$Arguments) {
    Push-Location $backend
    try {
        & $python @Arguments
    } finally {
        Pop-Location
    }
}

$apiOrigin = $env:API_ORIGIN
if (-not $apiOrigin) {
    $apiOrigin = Get-EnvSetting (Join-Path $frontend ".env.local") "API_ORIGIN"
}
if (-not $apiOrigin) {
    $apiOrigin = Get-EnvSetting (Join-Path $frontend ".env.local.example") "API_ORIGIN"
}
if (-not $apiOrigin) {
    throw "API_ORIGIN is not configured in frontend/.env.local or frontend/.env.local.example."
}
$apiUri = [uri]$apiOrigin
if ($apiUri.Scheme -ne "http" -or $apiUri.UserInfo -or $apiUri.Query -or $apiUri.Fragment) {
    throw "Local demo API_ORIGIN must be an HTTP origin without embedded credentials or query values."
}
$apiPort = $apiUri.Port
$apiBase = $apiUri.GetLeftPart([System.UriPartial]::Authority).TrimEnd('/')
$appUrl = "http://localhost:$webPort"
$apiHost = "127.0.0.1"
$webHost = "127.0.0.1"

$oldDemoMode = $env:DEMO_MODE
$oldPublicUrl = $env:PUBLIC_APP_URL
$oldCorsOrigins = $env:CORS_ORIGINS
$oldApiOrigin = $env:API_ORIGIN
$preflight = Invoke-BackendPython @("-c", "from app.config import settings; print(settings.app_env)")
if ($LASTEXITCODE -ne 0 -or ($preflight | Select-Object -Last 1) -ne "development") {
    throw "Refusing demo startup: the configured backend must already use APP_ENV=development. No database was changed."
}

try {
    if ($LanHost) {
        $appUrl = "http://${LanHost}:$webPort"
        $webHost = "0.0.0.0"
        $env:PUBLIC_APP_URL = $appUrl
        $originJson = Invoke-BackendPython @("-c", "import json; from app.config import settings; print(json.dumps(list(dict.fromkeys([*settings.cors_origins, '$appUrl']))))")
        if ($LASTEXITCODE -ne 0) { throw "Could not prepare the local-network origin allowlist." }
        $env:CORS_ORIGINS = ($originJson | Select-Object -Last 1)
    }

    $env:DEMO_MODE = "true"
    $env:API_ORIGIN = $apiBase

    Push-Location $backend
    try {
        & $alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw "Alembic upgrade failed; existing records were not reset." }
        & $python $seed
        if ($LASTEXITCODE -ne 0) { throw "Demo seeding failed; existing records were not reset." }
    } finally {
        Pop-Location
    }

    $apiReady = Test-Ready "$apiBase/readyz"
    $apiDemo = $apiReady -and (Test-DemoEnabled $apiBase)
    if ($LanHost -and $apiDemo) {
        Stop-VerifiedBackend $apiPort
        $apiDemo = $false
    }
    if (-not $apiDemo) {
        $listener = Get-ProjectListener $apiPort
        if ($listener) { Stop-VerifiedBackend $apiPort }
        $apiArguments = @("app.main:app", "--host", $apiHost, "--port", "$apiPort", "--no-access-log")
        $apiErrorLog = Join-Path $env:TEMP ("medical-passport-api-" + [guid]::NewGuid().ToString("N") + ".err.log")
        Start-Process -FilePath $uvicorn -ArgumentList $apiArguments -WorkingDirectory $backend -WindowStyle Hidden -RedirectStandardOutput "NUL" -RedirectStandardError $apiErrorLog | Out-Null
        $limit = (Get-Date).AddSeconds(30)
        do {
            Start-Sleep -Milliseconds 500
            $apiDemo = (Test-Ready "$apiBase/readyz") -and (Test-DemoEnabled $apiBase)
        } until ($apiDemo -or (Get-Date) -ge $limit)
        if (-not $apiDemo) { throw "The backend did not become ready with demo mode enabled. Inspect the backend terminal configuration and database connection." }
    }

    $webDemo = (-not $LanHost) -and (Test-Ready $appUrl) -and (Test-DemoEnabled $appUrl)
    if (-not $webDemo) {
        $listener = Get-ProjectListener $webPort
        if ($listener) { Stop-VerifiedFrontend $webPort }
        $node = (Get-Command node.exe -ErrorAction Stop).Source
        $next = Join-Path $frontend "node_modules\next\dist\bin\next"
        $webArguments = @($next, "dev", "--hostname", $webHost, "--port", "$webPort")
        $webErrorLog = Join-Path $env:TEMP ("medical-passport-web-" + [guid]::NewGuid().ToString("N") + ".err.log")
        Start-Process -FilePath $node -ArgumentList $webArguments -WorkingDirectory $frontend -WindowStyle Hidden -RedirectStandardOutput "NUL" -RedirectStandardError $webErrorLog | Out-Null
        $limit = (Get-Date).AddSeconds(45)
        do {
            Start-Sleep -Milliseconds 500
            $webDemo = (Test-Ready $appUrl) -and (Test-DemoEnabled $appUrl)
        } until ($webDemo -or (Get-Date) -ge $limit)
        if (-not $webDemo) { throw "The frontend did not become ready with the configured API proxy. Check that the configured backend origin is reachable." }
    }

    Write-Host "Medical Passport demo is ready."
    Write-Host "Application: $appUrl"
    Write-Host "Demo login: demo@medicalpassport.local"
    Write-Host "Synthetic demo data only; not for clinical use."
    if ($LanHost) {
        Write-Host "For phone scanning, keep this computer and phone on the same trusted Wi-Fi network and allow port 3000 through Windows Firewall."
    }
} finally {
    $env:DEMO_MODE = $oldDemoMode
    $env:PUBLIC_APP_URL = $oldPublicUrl
    $env:CORS_ORIGINS = $oldCorsOrigins
    $env:API_ORIGIN = $oldApiOrigin
}
