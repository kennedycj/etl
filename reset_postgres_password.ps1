# PowerShell script to reset PostgreSQL postgres user password
# Run as Administrator

Write-Host "PostgreSQL Password Reset Script" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Find PostgreSQL service
$postgresServices = Get-Service | Where-Object {$_.Name -like "*postgresql*"}
if (-not $postgresServices) {
    Write-Host "Error: Could not find PostgreSQL service" -ForegroundColor Red
    Write-Host "Make sure PostgreSQL is installed" -ForegroundColor Yellow
    exit 1
}

Write-Host "Found PostgreSQL service(s):" -ForegroundColor Green
$postgresServices | Format-Table Name, Status, DisplayName

$serviceName = $postgresServices[0].Name
Write-Host "Using service: $serviceName" -ForegroundColor Yellow
Write-Host ""

# Find PostgreSQL data directory
$postgresPath = "C:\Program Files\PostgreSQL"
if (-not (Test-Path $postgresPath)) {
    $postgresPath = "C:\Program Files (x86)\PostgreSQL"
    if (-not (Test-Path $postgresPath)) {
        Write-Host "Error: Could not find PostgreSQL installation directory" -ForegroundColor Red
        exit 1
    }
}

# Get version directories
$versionDirs = Get-ChildItem -Path $postgresPath -Directory | Where-Object {$_.Name -match '^\d+$'}
if (-not $versionDirs) {
    Write-Host "Error: Could not find PostgreSQL version directory" -ForegroundColor Red
    exit 1
}

$latestVersion = ($versionDirs | Sort-Object Name -Descending)[0].Name
$dataDir = Join-Path $postgresPath $latestVersion "data"
$pgHbaFile = Join-Path $dataDir "pg_hba.conf"

Write-Host "PostgreSQL data directory: $dataDir" -ForegroundColor Green
Write-Host "pg_hba.conf file: $pgHbaFile" -ForegroundColor Green
Write-Host ""

if (-not (Test-Path $pgHbaFile)) {
    Write-Host "Error: Could not find pg_hba.conf file" -ForegroundColor Red
    exit 1
}

# Backup pg_hba.conf
$backupFile = "$pgHbaFile.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $pgHbaFile $backupFile
Write-Host "Backed up pg_hba.conf to: $backupFile" -ForegroundColor Green
Write-Host ""

# Read current pg_hba.conf
$pgHbaContent = Get-Content $pgHbaFile -Raw
$originalContent = $pgHbaContent

# Replace authentication methods with 'trust' for localhost connections
$pgHbaContent = $pgHbaContent -replace '(host\s+all\s+all\s+127\.0\.0\.1/32\s+)(md5|scram-sha-256|password)', '$1trust'
$pgHbaContent = $pgHbaContent -replace '(host\s+all\s+all\s+::1/128\s+)(md5|scram-sha-256|password)', '$1trust'
$pgHbaContent = $pgHbaContent -replace '(local\s+all\s+all\s+)(md5|scram-sha-256|password)', '$1trust'

if ($pgHbaContent -eq $originalContent) {
    Write-Host "Warning: Could not find authentication lines to modify" -ForegroundColor Yellow
    Write-Host "You may need to manually edit pg_hba.conf" -ForegroundColor Yellow
} else {
    # Write modified content
    Set-Content -Path $pgHbaFile -Value $pgHbaContent -NoNewline
    Write-Host "Modified pg_hba.conf to use 'trust' authentication" -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Restart PostgreSQL service (this script will prompt you)" -ForegroundColor Yellow
Write-Host "2. Connect: psql -U postgres" -ForegroundColor Yellow
Write-Host "3. Change password: ALTER USER postgres PASSWORD 'your_new_password';" -ForegroundColor Yellow
Write-Host "4. This script will restore the original pg_hba.conf" -ForegroundColor Yellow
Write-Host ""

$restart = Read-Host "Restart PostgreSQL service now? (y/n)"
if ($restart -eq 'y' -or $restart -eq 'Y') {
    Write-Host "Stopping PostgreSQL service..." -ForegroundColor Yellow
    Stop-Service $serviceName -Force
    Start-Sleep -Seconds 2
    
    Write-Host "Starting PostgreSQL service..." -ForegroundColor Yellow
    Start-Service $serviceName
    Start-Sleep -Seconds 3
    
    $serviceStatus = Get-Service $serviceName
    if ($serviceStatus.Status -eq 'Running') {
        Write-Host "PostgreSQL service is running" -ForegroundColor Green
    } else {
        Write-Host "Warning: PostgreSQL service may not be running properly" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=================================" -ForegroundColor Cyan
Write-Host "IMPORTANT: Change the password now!" -ForegroundColor Red
Write-Host ""
Write-Host "Run this command:" -ForegroundColor Yellow
Write-Host "  psql -U postgres" -ForegroundColor White
Write-Host ""
Write-Host "Then in psql, run:" -ForegroundColor Yellow
Write-Host "  ALTER USER postgres PASSWORD 'your_new_password';" -ForegroundColor White
Write-Host ""
Write-Host "After changing the password, run this script again with -Restore flag" -ForegroundColor Yellow
Write-Host "  .\reset_postgres_password.ps1 -Restore" -ForegroundColor White

param(
    [switch]$Restore
)

if ($Restore) {
    Write-Host "Restoring original pg_hba.conf..." -ForegroundColor Cyan
    $backupFiles = Get-ChildItem -Path (Split-Path $pgHbaFile) -Filter "pg_hba.conf.backup_*" | Sort-Object LastWriteTime -Descending
    if ($backupFiles) {
        $latestBackup = $backupFiles[0].FullName
        Copy-Item $latestBackup $pgHbaFile -Force
        Write-Host "Restored from: $latestBackup" -ForegroundColor Green
        
        Write-Host "Restarting PostgreSQL service..." -ForegroundColor Yellow
        Restart-Service $serviceName -Force
        Write-Host "Done! Original authentication settings restored." -ForegroundColor Green
    } else {
        Write-Host "Error: Could not find backup file" -ForegroundColor Red
    }
}

