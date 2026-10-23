# ==============================================================================
# Local Launcher for NCX Portal Emissions App (Zero GitHub Push Required)
# Runs on native Windows PowerShell with Python 3.14 + Application Default Creds
# ==============================================================================
$ErrorActionPreference = "Stop"

$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

# Set local development environment variables (simulates Cloud Run Direct IAP)
$env:APP_ENV = "local"
$env:APP_NAME = "ncx-portal-emissions-app"
$env:GCP_PROJECT_ID = if ($env:GCP_PROJECT_ID) { $env:GCP_PROJECT_ID } else { "tu-data-edw-pr-1" }
$env:BQ_LOCATION = "australia-southeast1"
$env:DEV_USER_EMAIL = if ($env:DEV_USER_EMAIL) { $env:DEV_USER_EMAIL } else { "$env:USERNAME@transurban.com" }

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Launching NCX Tunnel Ventilation & Portal Emission Analytics" -ForegroundColor Cyan
Write-Host " Mode:      Local Workstation (No GitHub Push Required)" -ForegroundColor Green
Write-Host " Identity:  $env:DEV_USER_EMAIL (Mock IAP Header)" -ForegroundColor Gray
Write-Host " Project:   $env:GCP_PROJECT_ID ($env:BQ_LOCATION)" -ForegroundColor Gray
Write-Host " URL:       http://localhost:8501" -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

& "C:\Program Files\Python314\python.exe" -m streamlit run src/app.py `
    --server.port=8501 `
    --server.address=localhost `
    --browser.gatherUsageStats=false
