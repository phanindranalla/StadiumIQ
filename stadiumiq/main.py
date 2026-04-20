"""
StadiumIQ — Main FastAPI Application

Serves the web UI and API endpoints for the smart venue assistant.
Run with: uvicorn main:app --host 0.0.0.0 --port 8080
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from agent import StadiumAgent
from tools import (
    get_crowd_density,
    get_queue_times,
    get_game_state,
    get_exit_strategy,
    get_venue_name,
)
from live_data import search_matches, set_active_match, get_active_match, is_live_mode, get_active_sport, SPORT_CONFIGS

# ── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="StadiumIQ",
    description="Smart Venue Experience Assistant for Large-Scale Sporting Events",
    version="1.0.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global agent instance
agent: StadiumAgent = None


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""
    message: str
    section: str = "A1"


class SelectMatchRequest(BaseModel):
    """Request body for the select-match endpoint."""
    fixture_id: str
    sport: str = "football"


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize the StadiumAgent on application startup."""
    global agent
    agent = StadiumAgent(user_section="A1")


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_index() -> HTMLResponse:
    """Serve the main web application page.

    Returns:
        The index.html file as an HTML response.
    """
    with open("static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.get("/api/venue-data")
async def get_venue_data() -> JSONResponse:
    """Get all live venue data in a single response.

    Calls crowd density, queue times, and game state tools
    and bundles them together. Includes venue name for dashboard display.

    Returns:
        JSON with keys: crowd, queues, game, venue_name, is_live.
    """
    return JSONResponse(content={
        "crowd": get_crowd_density(),
        "queues": get_queue_times(),
        "game": get_game_state(),
        "venue_name": get_venue_name(),
        "is_live": is_live_mode(),
    })


@app.get("/api/search-matches")
async def search_matches_endpoint(q: str = "", sport: str = "all") -> JSONResponse:
    """Search for live and upcoming matches by team/league name.

    Args:
        q: Search query string (team name, league, etc.).
        sport: Filter by sport ("football", "basketball", "cricket", "all").

    Returns:
        JSON with key: matches (list of match dicts).
    """
    if not q or len(q.strip()) < 2:
        return JSONResponse(content={"matches": [], "error": "Search query too short."})

    matches = search_matches(q.strip(), sport=sport)
    return JSONResponse(content={"matches": matches})


@app.post("/api/select-match")
async def select_match_endpoint(request: SelectMatchRequest) -> JSONResponse:
    """Select a match as the active fixture for the dashboard.

    Sets the active match, which causes all data endpoints to switch
    to live mode with real scores and simulated crowd data.

    Args:
        request: SelectMatchRequest with fixture_id and sport.

    Returns:
        JSON with the selected match info, or an error.
    """
    global agent

    result = set_active_match(request.fixture_id, sport=request.sport)
    if not result:
        return JSONResponse(
            status_code=400,
            content={"error": "Could not load match data. Check fixture ID or API key."},
        )

    # Reinitialize agent with fresh live data context
    agent = StadiumAgent(user_section=agent.user_section if agent else "A1")

    return JSONResponse(content={
        "match": result,
        "venue_name": result.get("venue_name", "Unknown Venue"),
        "sport": request.sport,
    })


@app.get("/api/active-match")
async def active_match_endpoint() -> JSONResponse:
    """Get the currently active match info.

    Returns:
        JSON with match info, venue name, sport, or null if no match selected.
    """
    match = get_active_match()
    if not match:
        return JSONResponse(content={"match": None, "venue_name": get_venue_name(), "is_live": False, "sport": "football"})

    return JSONResponse(content={
        "match": match,
        "venue_name": match.get("venue_name", get_venue_name()),
        "is_live": True,
        "sport": get_active_sport(),
    })


@app.get("/api/sports")
async def list_sports() -> JSONResponse:
    """List all supported sports with their configuration.

    Returns:
        JSON with available sports and their icons/labels.
    """
    sports = [
        {"id": k, "label": v["label"], "icon": v["icon"]}
        for k, v in SPORT_CONFIGS.items()
    ]
    return JSONResponse(content={"sports": sports})


@app.get("/api/config")
async def get_config() -> JSONResponse:
    """Provides public frontend configuration parameters exactly as requested.

    Returns:
        JSON with configuration variables (e.g. maps_api_key).
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    return JSONResponse(content={"maps_api_key": maps_key})

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest) -> JSONResponse:
    """Process a chat message from the attendee.

    If the section has changed, reinitializes the agent with the new section.
    Returns the AI response and any proactive alert.

    Args:
        request: ChatRequest with message and section fields.

    Returns:
        JSON with keys: response (str), alert (str or null).
    """
    global agent

    # Reinitialize agent if section changed
    if request.section != agent.user_section:
        agent = StadiumAgent(user_section=request.section)

    response_text = agent.chat(request.message)
    alert = agent.get_proactive_alert()

    return JSONResponse(content={
        "response": response_text,
        "alert": alert,
    })


@app.get("/api/exit-strategy/{section}")
async def exit_strategy_endpoint(section: str) -> JSONResponse:
    """Get the exit strategy for a specific seat section.

    Args:
        section: The seat section identifier (e.g., "A1", "B2").

    Returns:
        JSON dict with recommended_gate, zone_name, estimated_wait, tip.
    """
    result = get_exit_strategy(section)
    return JSONResponse(content=result)


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint for monitoring and load balancers.

    Returns:
        JSON with status and service name.
    """
    return JSONResponse(content={
        "status": "ok",
        "service": "StadiumIQ",
    })


@app.get("/api/debug-keys")
async def debug_keys() -> JSONResponse:
    """Diagnostic endpoint to check API key loading on Cloud Run."""
    import os
    from live_data import _api_sports_request, _cricket_api_request
    
    football_key = os.getenv("FOOTBALL_API_KEY", "")
    cricket_key = os.getenv("CRICKET_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "")

    # Perform a quick test request to see if the network is blocking us or keys are invalid
    cricket_test = "Not tested"
    try:
        test_resp = _cricket_api_request("/currentMatches", {"offset": "0"})
        cricket_test = "Success" if test_resp else "Failed/Empty"
    except Exception as e:
        cricket_test = f"Error: {e}"

    return JSONResponse(content={
        "keys_present": {
            "football": len(football_key) > 5,
            "cricket": len(cricket_key) > 5,
            "gemini": len(gemini_key) > 5,
            "maps": len(maps_key) > 5,
        },
        "football_prefix": football_key[:4] if football_key else "None",
        "cricket_prefix": cricket_key[:4] if cricket_key else "None",
        "cricket_api_test": cricket_test,
    })
