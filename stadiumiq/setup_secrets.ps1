# StadiumIQ Secret Manager Setup Script
# This script creates secrets in GCP from your local .env file.

$ProjectID = "stadiumiq-493905"
Write-Host "Configuring Secret Manager for project: $ProjectID"

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Error "Google Cloud SDK (gcloud) is not installed."
    exit 1
}

gcloud config set project $ProjectID
gcloud services enable secretmanager.googleapis.com

# Get Project Number for Service Account permissions
$ProjectNumber = gcloud projects describe $ProjectID --format="value(projectNumber)"
$ServiceAccount = "$ProjectNumber-compute@developer.gserviceaccount.com"

# Parse .env file
$EnvFile = Get-Content .env
foreach ($Line in $EnvFile) {
    if ($Line -match "^(?<key>[^#=]+)=(?<value>.*)$") {
        $Key = $Matches["key"].Trim()
        $Value = $Matches["value"].Trim().Trim('"').Trim("'")

        if ($Key -and $Value) {
            Write-Host "Processing secret: $Key"
            
            # Create secret if it doesn't exist
            $exists = gcloud secrets list --filter="name:$Key" --format="value(name)"
            if (-not $exists) {
                gcloud secrets create $Key --replication-policy="automatic"
            }

            # Add version from value
            Write-Host "Adding value to $Key..."
            $Value | gcloud secrets versions add $Key --data-file=-

            # Grant access to Cloud Run service account
            Write-Host "Granting access to $ServiceAccount..."
            gcloud secrets add-iam-policy-binding $Key `
                --member="serviceAccount:$ServiceAccount" `
                --role="roles/secretmanager.secretAccessor"
        }
    }
}

Write-Host "Secret Manager setup complete!"
