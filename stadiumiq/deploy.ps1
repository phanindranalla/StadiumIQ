# StadiumIQ Deployment Script for Google Cloud Run (Secret Manager Version)
# This script automates the deployment process on Windows.

$ProjectID = "stadiumiq-493905"
$Region = "us-central1"

$ServiceAccount = "stadium-runner@stadiumiq-493905.iam.gserviceaccount.com"

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Error "Google Cloud SDK (gcloud) is not installed or not in your PATH."
    Write-Host "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
}

Write-Host "Checking GCP Project..."
gcloud config set project $ProjectID

Write-Host "Granting the Service Account permission to read secrets..."
gcloud projects add-iam-policy-binding $ProjectID `
    --member="serviceAccount:$ServiceAccount" `
    --role="roles/secretmanager.secretAccessor" | Out-Null

Write-Host "Enabling necessary services (Cloud Run, Artifact Registry, Cloud Build)..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

Write-Host "Deploying StadiumIQ to Cloud Run with Secret Manager..."
try {
    $ErrorActionPreference = "Stop"
    gcloud run deploy stadiumiq --source . --region=$Region --allow-unauthenticated --service-account=$ServiceAccount --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest,FOOTBALL_API_KEY=FOOTBALL_API_KEY:latest,CRICKET_API_KEY=CRICKET_API_KEY:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest,MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest"
    Write-Host "Deployment complete! Your service should be available shortly." -ForegroundColor Green
} catch {
    Write-Error "Deployment failed! Please check the red error text above. Do not assume the app is deployed."
}
