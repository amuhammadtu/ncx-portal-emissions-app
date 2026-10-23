# ==============================================================================
# Sync Live BigQuery (`tu-data-edw-pr-1.a113_roadside`) -> GitHub Pages URL
# Queries the latest 14 days of NCX telemetry & alarms, updates docs/index.html
# and docs/streamlit.html, and pushes to GitHub so your GitHub Pages URL updates.
# ==============================================================================
param(
    [string]$RemoteUrl = "",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Syncing Live BigQuery (a113_roadside) -> GitHub Pages Web App" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# Step 1: Query live BigQuery and rebuild index.html + docs/index.html + docs/streamlit.html
& "C:\Program Files\Python314\python.exe" "$AppDir\update_github_live_data.py"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to fetch live BigQuery data."
    exit $LASTEXITCODE
}

# Step 2: Ensure Git repository is initialized
if (-not (Test-Path "$AppDir\.git")) {
    Write-Host "`n[Git] Initializing git repository in $AppDir..." -ForegroundColor Yellow
    git init -b $Branch
}

if ($RemoteUrl) {
    $ExistingRemotes = git remote
    if ($ExistingRemotes -contains "origin") {
        git remote set-url origin $RemoteUrl
    } else {
        git remote add origin $RemoteUrl
    }
}

# Step 3: Stage and commit updated live BigQuery web app artifacts
git add index.html streamlit.html .nojekyll docs/ src/data/ncx_expanded_dashboard_payload.json .github/workflows/deploy-github-pages.yml update_github_live_data.py sync_bq_to_github.ps1
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
git commit -m "chore(bq-sync): update live a113_roadside telemetry snapshot ($Timestamp AEST)" --allow-empty

$OriginUrl = git remote get-url origin 2>$null
if ($OriginUrl) {
    Write-Host "`n[Git] Pushing live BigQuery web app to $OriginUrl ($Branch)..." -ForegroundColor Green
    git push -u origin $Branch
    Write-Host "`n[SUCCESS] Pushed to GitHub! Your GitHub Pages URL will update in ~30 seconds." -ForegroundColor Green
} else {
    Write-Host "`n[!] Git commit created locally, but no GitHub remote URL is configured yet." -ForegroundColor Yellow
    Write-Host "    Run with your GitHub repo URL to push:" -ForegroundColor Yellow
    Write-Host "    .\sync_bq_to_github.ps1 -RemoteUrl 'https://github.com/<org-or-user>/<repo>.git'" -ForegroundColor Cyan
}
