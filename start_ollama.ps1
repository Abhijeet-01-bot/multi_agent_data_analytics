$ErrorActionPreference = "Stop"

$OllamaExe = "C:\Users\Abhijeet.2.Kumar\OLLAMA\ollama.exe"
$ApiUrl = "http://127.0.0.1:11434/api/version"

$OutputLog = Join-Path $env:TEMP "ollama-server-output.log"
$ErrorLog = Join-Path $env:TEMP "ollama-server-error.log"
$OfficialLog = Join-Path $env:LOCALAPPDATA "Ollama\server.log"

if (-not (Test-Path $OllamaExe)) {
    Write-Host "Ollama executable was not found:" -ForegroundColor Red
    Write-Host $OllamaExe -ForegroundColor Red
    exit 1
}

Write-Host "Checking Ollama server..." -ForegroundColor Cyan

try {
    $VersionResponse = Invoke-RestMethod `
        -Uri $ApiUrl `
        -Method Get `
        -TimeoutSec 3

    Write-Host "Ollama is already running." -ForegroundColor Green
    Write-Host "Server version: $($VersionResponse.version)" -ForegroundColor Green

    Write-Host ""
    Write-Host "Installed models:" -ForegroundColor Cyan

    & $OllamaExe list

    exit 0
}
catch {
    Write-Host "Ollama server is not currently running." -ForegroundColor Yellow
}

Write-Host "Starting Ollama server..." -ForegroundColor Yellow

Remove-Item $OutputLog -Force -ErrorAction SilentlyContinue
Remove-Item $ErrorLog -Force -ErrorAction SilentlyContinue

try {
    $Process = Start-Process `
        -FilePath $OllamaExe `
        -ArgumentList "serve" `
        -WindowStyle Hidden `
        -RedirectStandardOutput $OutputLog `
        -RedirectStandardError $ErrorLog `
        -PassThru

    Write-Host "Ollama process ID: $($Process.Id)"
}
catch {
    Write-Host "Could not start the Ollama process." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

$ServerRunning = $false
$MaximumAttempts = 15

for ($Attempt = 1; $Attempt -le $MaximumAttempts; $Attempt++) {
    Start-Sleep -Seconds 2

    try {
        $VersionResponse = Invoke-RestMethod `
            -Uri $ApiUrl `
            -Method Get `
            -TimeoutSec 3

        $ServerRunning = $true

        Write-Host "Ollama server started successfully." -ForegroundColor Green
        Write-Host "Server version: $($VersionResponse.version)" -ForegroundColor Green

        break
    }
    catch {
        Write-Host "Waiting for Ollama: attempt $Attempt of $MaximumAttempts"
    }
}

if (-not $ServerRunning) {
    Write-Host ""
    Write-Host "Ollama did not start successfully." -ForegroundColor Red

    if (Test-Path $OutputLog) {
        Write-Host ""
        Write-Host "Ollama output log:" -ForegroundColor Yellow
        Get-Content $OutputLog -Tail 100
    }

    if (Test-Path $ErrorLog) {
        Write-Host ""
        Write-Host "Ollama error log:" -ForegroundColor Yellow
        Get-Content $ErrorLog -Tail 100
    }

    if (Test-Path $OfficialLog) {
        Write-Host ""
        Write-Host "Official Ollama server log:" -ForegroundColor Yellow
        Get-Content $OfficialLog -Tail 100
    }

    exit 1
}

Write-Host ""
Write-Host "Installed models:" -ForegroundColor Cyan

& $OllamaExe list