# PowerShell script to sync from GitHub to server using Git Bash
$localPath = "C:\Users\nikit\cod\content-factory"
$gitBashPath = "C:\Program Files\Git\bin\bash.exe"
$scriptPath = Join-Path $localPath "sync-to-server.sh"

# Проверяем наличие Git Bash
if (-not (Test-Path $gitBashPath)) {
    Write-Error "Git Bash not found at $gitBashPath. Please install Git for Windows first."
    exit 1
}

# Проверяем наличие скрипта
if (-not (Test-Path $scriptPath)) {
    Write-Error "Sync script not found at $scriptPath"
    exit 1
}

# Запускаем синхронизацию через Git Bash
try {
    & $gitBashPath $scriptPath
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Sync completed successfully"
    } else {
        Write-Error "Sync failed with exit code $LASTEXITCODE"
    }
} catch {
    Write-Error "Error during sync: $_"
} 