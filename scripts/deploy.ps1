<#
.SYNOPSIS
    Deploy DigitalCoach to Google Cloud Run from source (Cloud Build, no local Docker).

.DESCRIPTION
    Builds the image from the repo Dockerfile via Cloud Build, pushes to Artifact
    Registry, and rolls out a scale-to-zero Cloud Run service in me-west1.

    Prereqs (one-time): gcloud installed + `gcloud auth login`, billing enabled,
    and the run/cloudbuild/artifactregistry APIs enabled.

.EXAMPLE
    ./scripts/deploy.ps1
    ./scripts/deploy.ps1 -Project calisthenics-498018 -Region me-west1
#>
param(
    [string]$Project   = "calisthenics-498018",
    [string]$Region    = "me-west1",
    [string]$Service   = "digitalcoach",
    [string]$Memory    = "2Gi",
    [int]   $Cpu       = 2,
    [int]   $Timeout   = 600,
    [int]   $Concurrency = 1,
    [int]   $MinInstances = 0,
    [int]   $MaxInstances = 3
)

$ErrorActionPreference = "Stop"

# Run from the repo root regardless of where the script is invoked.
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Deploying '$Service' to Cloud Run ($Region, project $Project)..." -ForegroundColor Cyan

gcloud run deploy $Service `
    --source . `
    --quiet `
    --project $Project `
    --region $Region `
    --allow-unauthenticated `
    --memory $Memory `
    --cpu $Cpu `
    --timeout $Timeout `
    --concurrency $Concurrency `
    --min-instances $MinInstances `
    --max-instances $MaxInstances

if ($LASTEXITCODE -ne 0) { throw "Deploy failed (exit $LASTEXITCODE)." }

$url = gcloud run services describe $Service --project $Project --region $Region --format "value(status.url)"
Write-Host ""
Write-Host "Deployed. Service URL: $url" -ForegroundColor Green
Write-Host "Smoke test: curl $url/health" -ForegroundColor Green
