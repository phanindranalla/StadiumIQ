# StadiumIQ 🏟️

> Your Smart Venue Experience Assistant

## Chosen Vertical

Physical Event Experience — Large-Scale Sporting Venues

## Problem Statement

Attending a large-scale sporting event with 50,000+ spectators comes with real challenges: overcrowded food courts, long restroom queues, confusing exit routes, and no way to know what's happening around the venue in real time. Without intelligent coordination, attendees waste time in queues, miss key moments of the match, and face dangerous crowd bottlenecks during exits.

## Solution Overview

StadiumIQ is a web-based smart venue assistant that combines an AI-powered chat interface with live venue intelligence panels. Attendees select their seat section on arrival and immediately see real-time crowd density by zone, queue wait times for food courts and restrooms, and a personalized exit strategy. The Gemini 2.0 Flash-powered chatbot answers natural language questions with specific, data-driven advice — from "Where's the shortest food queue?" to "When should I leave to avoid the rush?" Proactive alerts fire automatically at half-time and during the final 10 minutes to help attendees plan ahead.

1. Attendee selects their seat section and searches for a live match (Football, Basketball, or Cricket)
2. Live panels show real-time scores, venue name, and dynamically simulated crowd data based on the match phase
3. Attendee asks questions in natural language
4. Gemini reasons over live venue context to give specific advice
5. Proactive alerts fire automatically at key match moments

## Architecture

```text
User Browser
    ↓
FastAPI (main.py)
    ├── /api/search-matches → live_data.py → Live sport APIs (api-sports.io / CricAPI)
    ├── /api/chat → agent.py → Gemini 2.0 Flash API (Aware of live venue/match state)
    ├── /api/venue-data → tools.py → live_data.py dynamic simulation (or fallback JSON)
    └── /static → index.html (Chat UI + Live Panels + Match Search)
```

## Google Services Used

| Service | Purpose |
|---|---|
| Gemini 2.0 Flash | Powers the AI chat assistant |
| Google Cloud Run | Hosts the deployable web application |
| Google Maps Embed API | Venue navigation map |
| Google Material Icons | UI icon system |
| Google Fonts (Inter) | Typography |

## Features

- **Multi-Sport Live Data**: Search and track real Football, Basketball, and Cricket matches
- **Dynamic Crowd Simulation**: Crowd density and queues simulate realistically based on the live match phase (e.g., halftime spikes, final 10-minute exit rushes)
- **AI-Powered Assistant**: Natural language venue assistant powered by Gemini 2.0 Flash
- **Real-Time Dashboards**: Live crowd density heatmap, queue wait times, and match status
- **Exit Strategy**: Personalised exit routing based on your seat section
- **Graceful Fallback**: App remains fully functional with static mock data if no API keys are provided

## How It Works

1. Attendee selects their seat section on arrival
2. Live panels show crowd density, queue times, game state
3. Attendee asks questions in natural language
4. Gemini reasons over live venue context to give specific advice
5. Proactive alerts fire automatically at key match moments

## Setup and Deployment

### Local Development

### Local Development

```bash
# Clone the repository
git clone https://github.com/your-username/stadiumiq.git
cd stadiumiq

# Create a .env file with your required API keys
# FOOTBALL_API_KEY supports both Football and Basketball via api-sports.io
# CRICKET_API_KEY is from cricapi.com
cat << EOF > .env
GEMINI_API_KEY=your_gemini_api_key_here
FOOTBALL_API_KEY=your_api_football_key_here
CRICKET_API_KEY=your_cricapi_key_here
EOF

# Install dependencies
pip install -r requirements.txt

# Run the development server
uvicorn main:app --reload --port 8080
```

Then open [http://localhost:8080](http://localhost:8080) in your browser.

### Deploy to Google Cloud Run

```bash
# Build and submit the container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/stadiumiq

# Deploy to Cloud Run
gcloud run deploy stadiumiq \
  --image gcr.io/YOUR_PROJECT_ID/stadiumiq \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_gemini_key,FOOTBALL_API_KEY=your_football_key,CRICKET_API_KEY=your_cricket_key
```

## Assumptions Made

- **Secondary Simulation**: While match scores and phases are real-time via external APIs, public APIs do not provide real venue *sensor* data. Therefore, crowd density and queue times are simulated dynamically in relative proportion to the live match phase.
- **Graceful Degradation**: If third-party sports APIs fail or no keys are provided, the application falls back safely to reading from `data/*.json`.

## Project Structure

```
stadiumiq/
├── main.py              # FastAPI application and routes
├── agent.py             # Gemini-powered AI assistant context injector
├── tools.py             # Venue intelligence functions & fallback router
├── live_data.py         # Multi-sport API integration & dynamic crowd simulation
├── data/
│   ├── venue.json       # Fallback stadium layout and facilities
│   ├── queue_times.json # Fallback crowd and queue data
│   └── game_state.json  # Fallback match state
├── static/
│   └── index.html       # Web UI (chat, live panels, match search)
├── tests/
│   └── test_tools.py    # Unit tests for tools and mock live_data logic
├── Dockerfile           # Production container for Cloud Run
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Testing

Run tests with:

```bash
python -m pytest tests/
```
