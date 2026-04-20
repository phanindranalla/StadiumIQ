# StadiumIQ 🏟️
> Your Smart Venue Companion — Know before you go. 
> Move before the crowd.

**Live Demo**: [YOUR_CLOUD_RUN_URL]

## Challenge Vertical
Physical Event Experience — Large-Scale Sporting Venues

## Problem Statement
Large sporting venues with 50,000+ attendees face three critical challenges that degrade the fan experience:
1. **Crowd Movement** — No visibility into congestion build-up across zones until it becomes a safety issue.
2. **Waiting Times** — Unpredictable food and restroom queues cause attendees to miss live action.
3. **Real-time Coordination** — No dynamic communication between venue systems and individual attendees.

## How StadiumIQ Solves This
- **Crowd Movement** is managed through the **Zone Density Heatmap** which provides real-time congestion visibility.
- **Waiting Times** are mitigated by **Queue Wait Time Panels** that help fans choose the fastest facilities.
- **Real-time Coordination** is achieved via the **AI Assistant + Proactive Alerts** system for personalized guidance.

## Architecture Diagram
```text
Browser → FastAPI → Gemini API 
                  → Firebase DB
                  → Static Files
```

## Google Services Used
| Service | Purpose |
|---|---|
| Gemini 2.5 Flash | Powers the intelligent venue assistant and natural language processing |
| Google Cloud Run | Scalable, serverless hosting for the application backend and frontend |
| Firebase Realtime Database | Dynamic storage for live crowd density and queue wait times |
| Google Maps Embed API | Integrated venue mapping and navigation display |
| Google Material Icons | Consistent, modern visual language for the dashboard interface |
| Google Fonts (Inter) | High-readability typography for information-dense panels |

## Features
- **Live Match Tracking**: Real-time scores and status for Football, Basketball, and Cricket fixtures.
- **AI Venue Assistant**: Natural language chat for facility locations, queue advice, and general venue help.
- **Dynamic Heatmap**: Visualization of zone-by-zone crowd density to help fans avoid bottlenecks.
- **Predictive Queues**: Time-accurate wait estimates for food and restrooms synchronized with match phases.
- **Personalized Exits**: Custom exit strategies and gate recommendations based on the fan's specific seat section.
- **Proactive Alerts**: Automatic notifications triggered at halftime and during the final 10 minutes for movement planning.

## Setup Instructions

### Local Development
1. **Clone the repository**: `git clone <repo-url>`
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Configure Environment**: Create a `.env` file with `GEMINI_API_KEY`, `MAPS_API_KEY`, `FIREBASE_DB_URL`, and `FIREBASE_CREDENTIALS_JSON`.
4. **Run Server**: `uvicorn main:app --reload --port 8080`

### Google Cloud Run Deployment
1. **Build Container**: `gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/stadiumiq`
2. **Deploy Service**:
   ```bash
   gcloud run deploy stadiumiq \
     --image gcr.io/YOUR_PROJECT_ID/stadiumiq \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars="GEMINI_API_KEY=...,MAPS_API_KEY=...,FIREBASE_DB_URL=...,FIREBASE_CREDENTIALS_JSON=..."
   ```

## Assumptions
1. **Dynamic Simulation**: Crowd and queue data are simulated in real-time relative to match phase (e.g., spikes during halftime) when live sensor data is unavailable.
2. **Venue Stand-in**: Wembley Stadium is used as the default interactive coordinate set for the Google Maps embed to represent a high-capacity venue.
3. **Graceful Fallback**: The application is designed to fall back to local mock JSON data if Firebase or external Sports APIs are unreachable.

## Challenge Alignment
Explicitly mapping requirements to features:
- **"crowd movement"** → Zone Density Heatmap for real-time congestion awareness.
- **"waiting times"** → Queue Wait Time Panels providing actionable facility metrics.
- **"real-time coordination"** → AI Assistant + Proactive Alerts for dynamic fan communication.
- **"seamless and enjoyable experience"** → Single URL access, no-install PWA-friendly design, mobile-responsive layout, and accessible UI.
