# StadiumIQ Deployment Guide 🚀

Follow these instructions to deploy the StadiumIQ Smart Venue Assistant to Google Cloud Run.

## Prerequisites

1.  **Google Cloud Project**: Ensure you have an active GCP project.
2.  **gcloud CLI**: Installed and authenticated (`gcloud auth login`).
3.  **Required APIs**: Enable the following services in your GCP Console:
    -   Cloud Build API
    -   Cloud Run API

## Deployment Steps

### 1. Build and Submit the Container

Run the following command from the root of the project to build the Docker image using Cloud Build:

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/stadiumiq
```

*Replace `YOUR_PROJECT_ID` with your actual Google Cloud Project ID.*

### 2. Deploy to Cloud Run

Deploy the container image to Cloud Run with the necessary environment variables:

```bash
gcloud run deploy stadiumiq \
  --image gcr.io/YOUR_PROJECT_ID/stadiumiq \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GEMINI_API_KEY=your_gemini_key,\
FIREBASE_DB_URL=https://your-project.firebaseio.com,\
FIREBASE_CREDENTIALS_JSON='{\"type\": \"service_account\", ...}',\
MAPS_API_KEY=your_maps_key"
```

### Required Environment Variables

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Your Google AI Studio / Gemini API key. |
| `FIREBASE_DB_URL` | The URL for your Firebase Realtime Database. |
| `FIREBASE_CREDENTIALS_JSON` | The full service account JSON key for Firebase as a string. |
| `MAPS_API_KEY` | Your Google Maps Embed/Javascript API key. |

> [!NOTE]
> Ensure `FIREBASE_CREDENTIALS_JSON` is properly escaped when setting via the command line or use the GCP Console to set it.

## Post-Deployment

### Expected URL Format
Once deployed, Cloud Run will provide a service URL in the format:
`https://stadiumiq-xxxxxx-uc.a.run.app`

### Health Check
Verification of service health can be done at:
`GET /health`

The expected response is:
```json
{
  "status": "ok",
  "service": "StadiumIQ"
}
```
