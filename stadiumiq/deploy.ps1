# StadiumIQ Deployment Script for Google Cloud Run (Secret Manager Version)
# This script automates the deployment process on Windows.

$ProjectID = "stadiumiq-493905"
$Region = "us-central1"

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Error "Google Cloud SDK (gcloud) is not installed or not in your PATH."
    Write-Host "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
}

Write-Host "Checking GCP Project..."
gcloud config set project $ProjectID

Write-Host "Enabling necessary services (Cloud Run, Artifact Registry, Cloud Build)..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

# Deploying to Cloud Run using Secretary Manager
Write-Host "Deploying StadiumIQ to Cloud Run with Secret Manager..."
gcloud run deploy stadiumiq `
    --source . `
    --region $Region `
    --allow-unauthenticated `
    --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,FOOTBALL_API_KEY=FOOTBALL_API_KEY:latest,CRICKET_API_KEY=CRICKET_API_KEY:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest"

Write-Host "Deployment complete! Your service should be available shortly."
