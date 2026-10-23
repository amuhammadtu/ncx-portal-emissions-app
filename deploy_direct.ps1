# ==============================================================================
# Direct Cloud Run Deployer (Zero GitHub Push / Zero CI/CD Required)
# Uploads your local folder directly to Google Cloud Build & Cloud Run v2
# ==============================================================================
param(
    [string]$ProjectId = "tu-roads-watertreatment-sb-1",
    [string]$BqProjectId = "tu-data-edw-pr-1",
    [string]$Region = "australia-southeast1",
    [string]$ServiceName = "ncx-portal-emissions-app",
    [string]$EnvName = "dev",
    [switch]$EnableIap = $true
)

$ErrorActionPreference = "Stop"
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AppDir

# Resolve gcloud.cmd from PATH or standard Windows user-space install locations
$GcloudCandidates = @(
    "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
    "$env:USERPROFILE\google-cloud-sdk\bin\gcloud.cmd",
    "$env:USERPROFILE\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
    "C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
    "C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
)

$GcloudBin = $null
$CmdInPath = Get-Command "gcloud" -ErrorAction SilentlyContinue
if ($CmdInPath) {
    $GcloudBin = $CmdInPath.Source
} else {
    foreach ($Candidate in $GcloudCandidates) {
        if (Test-Path $Candidate) {
            $GcloudBin = $Candidate
            break
        }
    }
}

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Option 2: Direct Cloud Run Deployment (No GitHub Push)" -ForegroundColor Cyan
Write-Host " Service:   $ServiceName ($EnvName)" -ForegroundColor Green
Write-Host " Project:   $ProjectId ($Region)" -ForegroundColor Gray
Write-Host " Data Mode: Live BigQuery (tu-data-edw-pr-1.a113_roadside)" -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

if (-not $GcloudBin) {
    Write-Host "`n[i] gcloud.cmd not found in PATH -- using Pure-Python ADC Cloud Run v2 Deployer (deploy_cloudrun_adc.py)..." -ForegroundColor Yellow
    & "C:\Program Files\Python314\python.exe" "$AppDir\deploy_cloudrun_adc.py" `
        --project-id $ProjectId `
        --bq-project-id $BqProjectId `
        --region $Region `
        --service-name $ServiceName `
        --env $EnvName
    exit $LASTEXITCODE
}

$DeployArgs = @(
    "beta", "run", "deploy", $ServiceName,
    "--source", ".",
    "--project", $ProjectId,
    "--region", $Region,
    "--platform", "managed",
    "--execution-environment", "gen2",
    "--port", "8080",
    "--cpu", "1",
    "--memory", "1Gi",
    "--min-instances", "0",
    "--max-instances", "5",
    "--session-affinity",
    "--no-allow-unauthenticated",
    "--set-env-vars", "APP_NAME=$ServiceName,APP_ENV=$EnvName,GCP_PROJECT_ID=$BqProjectId,BQ_LOCATION=$Region,DEFAULT_DATA_MODE=live_bigquery"
)

if ($EnableIap) {
    $DeployArgs += "--iap"
}

Write-Host "Executing: $GcloudBin $($DeployArgs -join ' ')" -ForegroundColor Yellow
& $GcloudBin @DeployArgs
