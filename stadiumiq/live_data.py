"""
StadiumIQ Live Data Module — Multi-Sport Support

Supports Football, Basketball, and Cricket via sport-specific API adapters.
- Football: api-sports.io (v3.football)
- Basketball: api-sports.io (v1.basketball) — same API key
- Cricket: cricketdata.org (separate free key)

Dynamically simulates crowd density and queue wait times based on real match
state. Falls back to static JSON files when no live data is available.
"""

import hashlib
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

# ── API Configuration ────────────────────────────────────────────────────────

# Helper to get keys dynamically (ensures they are fresh from environment)
def _get_api_sports_key(): return os.getenv("FOOTBALL_API_KEY", "")
def _get_cricket_api_key(): return os.getenv("CRICKET_API_KEY", "")

# Sport-specific API configurations
SPORT_CONFIGS = {
    "football": {
        "base_url": "https://v3.football.api-sports.io",
        "icon": "sports_soccer",
        "label": "Football",
        "api_key_env": "FOOTBALL_API_KEY",
    },
    "basketball": {
        "base_url": "https://v1.basketball.api-sports.io",
        "icon": "sports_basketball",
        "label": "Basketball",
        "api_key_env": "FOOTBALL_API_KEY",  # Same key works
    },
    "cricket": {
        "base_url": "https://api.cricapi.com/v1",
        "icon": "sports_cricket",
        "label": "Cricket",
        "api_key_env": "CRICKET_API_KEY",
    },
}

# ── Global State ─────────────────────────────────────────────────────────────

_active_fixture: Optional[Dict[str, Any]] = None
_active_venue: Optional[Dict[str, Any]] = None
_active_sport: str = "football"
_cached_fixture_data: Optional[Dict[str, Any]] = None
_cache_timestamp: float = 0
CACHE_TTL_SECONDS = 15


# ── Generic API Request ──────────────────────────────────────────────────────

def _api_sports_request(base_url: str, endpoint: str, params: Dict[str, str]) -> Optional[dict]:
    """Make a GET request to an api-sports.io API.

    Args:
        base_url: The sport-specific base URL.
        endpoint: The API endpoint path.
        params: Query parameters.

    Returns:
        Parsed JSON response dict, or None if the request fails.
    """
    key = _get_api_sports_key()
    if not key:
        return None
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{base_url}{endpoint}",
                headers={"x-apisports-key": key},
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            return data
    except Exception:
        return None


def _cricket_api_request(endpoint: str, params: Dict[str, str]) -> Optional[dict]:
    """Make a GET request to the Cricket API (cricapi.com).

    Args:
        endpoint: The API endpoint path.
        params: Query parameters.

    Returns:
        Parsed JSON response dict, or None if the request fails.
    """
    key = _get_cricket_api_key()
    if not key:
        return None
    try:
        params["apikey"] = key
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"https://api.cricapi.com/v1{endpoint}",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            return data if data.get("status") == "success" else None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# FOOTBALL ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

def _search_football(query: str) -> List[dict]:
    """Search for football matches."""
    results = []
    query_lower = query.lower()
    base = SPORT_CONFIGS["football"]["base_url"]

    # Live fixtures
    live_data = _api_sports_request(base, "/fixtures", {"live": "all"})
    if live_data and live_data.get("response"):
        for fix in live_data["response"]:
            home = fix["teams"]["home"]["name"]
            away = fix["teams"]["away"]["name"]
            league = fix["league"]["name"]
            venue_name = fix.get("fixture", {}).get("venue", {}).get("name", "")
            searchable = f"{home} {away} {league} {venue_name}".lower()
            if query_lower in searchable:
                results.append(_format_football_fixture(fix, is_live=True))

    # Upcoming fixtures (next 7 days) if nothing found for today
    if not results:
        from datetime import timedelta
        for i in range(1, 8):
            future_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
            future_data = _api_sports_request(base, "/fixtures", {"date": future_date})
            if future_data and future_data.get("response"):
                for fix in future_data["response"]:
                    home = fix["teams"]["home"]["name"]
                    away = fix["teams"]["away"]["name"]
                    league = fix["league"]["name"]
                    searchable = f"{home} {away} {league}".lower()
                    if query_lower in searchable:
                        results.append(_format_football_fixture(fix, is_live=False))
            if len(results) >= 5: break

    return results


def _format_football_fixture(fix: dict, is_live: bool = False) -> dict:
    """Format a raw football fixture into our standard structure."""
    fi = fix.get("fixture", {})
    teams = fix.get("teams", {})
    goals = fix.get("goals", {})
    league = fix.get("league", {})
    venue = fi.get("venue", {})
    status = fi.get("status", {})

    return {
        "fixture_id": fi.get("id"),
        "sport": "football",
        "home_team": teams.get("home", {}).get("name", "Home"),
        "away_team": teams.get("away", {}).get("name", "Away"),
        "home_logo": teams.get("home", {}).get("logo", ""),
        "away_logo": teams.get("away", {}).get("logo", ""),
        "league": league.get("name", "Unknown League"),
        "league_country": league.get("country", ""),
        "venue_name": venue.get("name", "Unknown Venue"),
        "venue_city": venue.get("city", ""),
        "status": status.get("long", "Unknown"),
        "status_short": status.get("short", "NS"),
        "score_home": goals.get("home"),
        "score_away": goals.get("away"),
        "elapsed": status.get("elapsed"),
        "date": fi.get("date", ""),
        "is_live": is_live or status.get("short") in ("1H", "HT", "2H", "ET", "P", "BT", "LIVE"),
    }


def _football_game_state(fixture: dict) -> dict:
    """Build game state dict from a football fixture."""
    elapsed = fixture.get("elapsed") or 0
    ss = fixture.get("status_short", "NS")

    time_remaining = {
        "1H": max(0, 90 - elapsed), "2H": max(0, 90 - elapsed),
        "HT": 45, "FT": 0, "AET": 0, "PEN": 0,
    }.get(ss, max(0, 90 - elapsed) if elapsed else 90)

    period_map = {
        "1H": "First Half", "2H": "Second Half", "HT": "Half-Time",
        "FT": "Full-Time", "AET": "After Extra Time", "PEN": "Penalties",
        "NS": "Not Started", "ET": "Extra Time", "P": "Penalty Shootout",
        "BT": "Break Time", "LIVE": "Live",
    }

    return {
        "period": period_map.get(ss, fixture.get("status", "Unknown")),
        "elapsed_minutes": elapsed,
        "time_remaining_minutes": time_remaining,
        "is_halftime": ss == "HT",
        "is_final_10_minutes": ss == "2H" and elapsed is not None and elapsed >= 80,
        "post_match_exit_open": ss in ("FT", "AET", "PEN"),
    }


def _football_phase(fixture: dict) -> str:
    """Determine the crowd simulation phase for football."""
    if not fixture or not fixture.get("is_live"):
        if fixture and fixture.get("status_short") in ("FT", "AET", "PEN"):
            return "post_match"
        return "pre_match"
    ss = fixture.get("status_short", "")
    elapsed = fixture.get("elapsed") or 0
    if ss == "HT": return "halftime"
    if ss == "1H": return "first_half"
    if ss == "2H": return "final_10" if elapsed >= 80 else "second_half"
    if ss in ("FT", "AET", "PEN"): return "post_match"
    if ss in ("ET", "BT", "P"): return "extra_time"
    return "second_half"


# ══════════════════════════════════════════════════════════════════════════════
# BASKETBALL ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

def _search_basketball(query: str) -> List[dict]:
    """Search for basketball games."""
    results = []
    query_lower = query.lower()
    base = SPORT_CONFIGS["basketball"]["base_url"]

    # Live games
    live_data = _api_sports_request(base, "/games", {"live": "all"})
    if live_data and live_data.get("response"):
        for game in live_data["response"]:
            formatted = _format_basketball_game(game, is_live=True)
            searchable = f"{formatted['home_team']} {formatted['away_team']} {formatted['league']}".lower()
            if query_lower in searchable:
                results.append(formatted)

    # Upcoming games if nothing found for today
    if not results:
        from datetime import timedelta
        for i in range(1, 4):
            future_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
            future_data = _api_sports_request(base, "/games", {"date": future_date})
            if future_data and future_data.get("response"):
                for game in future_data["response"]:
                    formatted = _format_basketball_game(game, is_live=False)
                    searchable = f"{formatted['home_team']} {formatted['away_team']} {formatted['league']}".lower()
                    if query_lower in searchable:
                        results.append(formatted)
            if len(results) >= 5: break

    return results


def _format_basketball_game(game: dict, is_live: bool = False) -> dict:
    """Format a raw basketball game into our standard structure."""
    teams = game.get("teams", {})
    scores = game.get("scores", {})
    league = game.get("league", {})
    status = game.get("status", {})
    country = game.get("country", {})

    home_score = scores.get("home", {}).get("total")
    away_score = scores.get("away", {}).get("total")

    # Determine venue — basketball API doesn't always provide venue
    venue_name = game.get("arena", {}).get("name", "") if game.get("arena") else ""
    if not venue_name:
        venue_name = f"{teams.get('home', {}).get('name', 'Home')} Arena"

    status_short = status.get("short")
    is_game_live = is_live or status_short in ("Q1", "Q2", "Q3", "Q4", "OT", "BT", "HT")

    return {
        "fixture_id": game.get("id"),
        "sport": "basketball",
        "home_team": teams.get("home", {}).get("name", "Home"),
        "away_team": teams.get("away", {}).get("name", "Away"),
        "home_logo": teams.get("home", {}).get("logo", ""),
        "away_logo": teams.get("away", {}).get("logo", ""),
        "league": league.get("name", "Unknown League"),
        "league_country": country.get("name", "") if isinstance(country, dict) else str(country),
        "venue_name": venue_name,
        "venue_city": "",
        "status": status.get("long", "Unknown"),
        "status_short": status_short or "NS",
        "score_home": home_score,
        "score_away": away_score,
        "elapsed": status.get("timer"),
        "date": game.get("date", ""),
        "is_live": is_game_live,
    }


def _basketball_game_state(fixture: dict) -> dict:
    """Build game state dict from a basketball fixture."""
    ss = fixture.get("status_short", "NS")
    elapsed = fixture.get("elapsed") or 0

    # Basketball: 4 quarters of 12 min (NBA) or 10 min (FIBA) = ~48 min total
    quarter_map = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "OT": 5}
    current_q = quarter_map.get(ss, 0)
    time_remaining = max(0, 48 - (current_q * 12)) if current_q else 48

    period_map = {
        "Q1": "1st Quarter", "Q2": "2nd Quarter", "Q3": "3rd Quarter",
        "Q4": "4th Quarter", "OT": "Overtime", "BT": "Break",
        "HT": "Half-Time", "FT": "Final", "NS": "Not Started",
        "AOT": "After Overtime",
    }

    is_halftime = ss in ("HT", "BT")
    is_final = ss == "Q4" and current_q == 4

    return {
        "period": period_map.get(ss, fixture.get("status", "Unknown")),
        "elapsed_minutes": elapsed,
        "time_remaining_minutes": time_remaining,
        "is_halftime": is_halftime,
        "is_final_10_minutes": is_final,
        "post_match_exit_open": ss in ("FT", "AOT"),
    }


def _basketball_phase(fixture: dict) -> str:
    """Determine crowd simulation phase for basketball."""
    if not fixture or not fixture.get("is_live"):
        if fixture and fixture.get("status_short") in ("FT", "AOT"):
            return "post_match"
        return "pre_match"
    ss = fixture.get("status_short", "")
    if ss in ("HT", "BT"): return "halftime"
    if ss in ("Q1", "Q2"): return "first_half"
    if ss == "Q4": return "final_10"
    if ss == "Q3": return "second_half"
    if ss in ("FT", "AOT"): return "post_match"
    if ss == "OT": return "extra_time"
    return "second_half"


# ══════════════════════════════════════════════════════════════════════════════
# CRICKET ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

def _search_cricket(query: str) -> List[dict]:
    """Search for cricket matches using CricAPI."""
    results = []
    query_lower = query.lower()

    data = _cricket_api_request("/currentMatches", {"offset": "0"})
    if not data or not data.get("data"):
        # Fallback: try match list
        data = _cricket_api_request("/matches", {"offset": "0"})

    if data and data.get("data"):
        for match in data["data"]:
            formatted = _format_cricket_match(match)
            if not formatted:
                continue
            searchable = f"{formatted['home_team']} {formatted['away_team']} {formatted['league']}".lower()
            if query_lower in searchable:
                results.append(formatted)

    return results


def _format_cricket_match(match: dict) -> Optional[dict]:
    """Format a raw cricket match into our standard structure."""
    if not match.get("id"):
        return None

    teams = match.get("teams", [])
    team_info = match.get("teamInfo", [])
    home_team = teams[0] if len(teams) > 0 else "Team A"
    away_team = teams[1] if len(teams) > 1 else "Team B"

    home_logo = team_info[0].get("img", "") if len(team_info) > 0 else ""
    away_logo = team_info[1].get("img", "") if len(team_info) > 1 else ""

    score_parts = match.get("score", [])
    home_score = score_parts[0].get("r", "") if len(score_parts) > 0 else ""
    away_score = score_parts[1].get("r", "") if len(score_parts) > 1 else ""

    match_status = match.get("status", "")
    is_live = match.get("matchStarted", False) and not match.get("matchEnded", False)

    return {
        "fixture_id": match.get("id"),
        "sport": "cricket",
        "home_team": home_team,
        "away_team": away_team,
        "home_logo": home_logo,
        "away_logo": away_logo,
        "league": match.get("series", match.get("name", "Cricket Match")),
        "league_country": "",
        "venue_name": match.get("venue", "Cricket Ground"),
        "venue_city": "",
        "status": match_status,
        "status_short": "LIVE" if is_live else ("FT" if match.get("matchEnded") else "NS"),
        "score_home": home_score if home_score else None,
        "score_away": away_score if away_score else None,
        "elapsed": None,
        "date": match.get("date", ""),
        "is_live": is_live,
    }


def _cricket_game_state(fixture: dict) -> dict:
    """Build game state dict from a cricket fixture."""
    is_live = fixture.get("is_live", False)
    status = fixture.get("status", "")
    ended = fixture.get("status_short") == "FT"

    # Cricket matches are long — estimate time remaining loosely
    time_remaining = 0 if ended else 180 if is_live else 300

    return {
        "period": status if status else ("Live" if is_live else "Scheduled"),
        "elapsed_minutes": None,
        "time_remaining_minutes": time_remaining,
        "is_halftime": False,  # Cricket uses innings breaks
        "is_final_10_minutes": False,
        "post_match_exit_open": ended,
    }


def _cricket_phase(fixture: dict) -> str:
    """Determine crowd simulation phase for cricket."""
    if not fixture or not fixture.get("is_live"):
        if fixture and fixture.get("status_short") == "FT":
            return "post_match"
        return "pre_match"
    # Cricket is long — use status text to approximate
    status = (fixture.get("status", "") or "").lower()
    if "innings break" in status or "break" in status:
        return "halftime"
    return "second_half"  # Steady crowd during play


# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED API
# ══════════════════════════════════════════════════════════════════════════════

def search_matches(query: str, sport: str = "all") -> List[dict]:
    """Search for matches across one or all supported sports.

    Args:
        query: Search term — team name, league, or keyword.
        sport: "football", "basketball", "cricket", or "all".

    Returns:
        List of match dicts sorted by live matches first.
    """
    results = []

    if sport in ("all", "football"):
        results.extend(_search_football(query))
    if sport in ("all", "basketball"):
        results.extend(_search_basketball(query))
    if sport in ("all", "cricket"):
        results.extend(_search_cricket(query))

    # Sort: live first, then by date
    results.sort(key=lambda m: (0 if m.get("is_live") else 1, m.get("date", "")))
    return results[:20]


def set_active_match(fixture_id, sport: str = "football") -> Optional[dict]:
    """Set the active match by fixture ID and sport.

    Args:
        fixture_id: The fixture/game ID from the sport API.
        sport: The sport type.

    Returns:
        The formatted fixture dict if successful, None otherwise.
    """
    global _active_fixture, _active_venue, _active_sport, _cached_fixture_data, _cache_timestamp

    _active_sport = sport

    if sport == "football":
        base = SPORT_CONFIGS["football"]["base_url"]
        data = _api_sports_request(base, "/fixtures", {"id": str(fixture_id)})
        if not data or not data.get("response"):
            return None
        fix = data["response"][0]
        _active_fixture = _format_football_fixture(fix)
        _cached_fixture_data = fix
        venue_name = fix.get("fixture", {}).get("venue", {}).get("name", "Stadium")

    elif sport == "basketball":
        base = SPORT_CONFIGS["basketball"]["base_url"]
        data = _api_sports_request(base, "/games", {"id": str(fixture_id)})
        if not data or not data.get("response"):
            return None
        game = data["response"][0]
        _active_fixture = _format_basketball_game(game)
        _cached_fixture_data = game
        venue_name = _active_fixture.get("venue_name", "Arena")

    elif sport == "cricket":
        data = _cricket_api_request("/match_info", {"id": str(fixture_id)})
        if not data or not data.get("data"):
            return None
        match = data["data"]
        _active_fixture = _format_cricket_match(match)
        if not _active_fixture:
            return None
        _cached_fixture_data = match
        venue_name = _active_fixture.get("venue_name", "Cricket Ground")

    else:
        return None

    _cache_timestamp = time.time()
    _active_venue = build_venue_layout(venue_name)
    return _active_fixture


def get_active_match() -> Optional[dict]:
    """Get the currently active match info."""
    return _active_fixture


def get_active_venue() -> Optional[dict]:
    """Get the current venue layout."""
    return _active_venue


def get_active_sport() -> str:
    """Get the currently active sport type."""
    return _active_sport


def refresh_live_fixture() -> Optional[dict]:
    """Refresh the live fixture data from the API (with caching)."""
    global _active_fixture, _cached_fixture_data, _cache_timestamp

    if not _active_fixture:
        return None

    if time.time() - _cache_timestamp < CACHE_TTL_SECONDS:
        return _active_fixture

    fixture_id = _active_fixture["fixture_id"]
    sport = _active_fixture.get("sport", _active_sport)

    if sport == "football":
        base = SPORT_CONFIGS["football"]["base_url"]
        data = _api_sports_request(base, "/fixtures", {"id": str(fixture_id)})
        if data and data.get("response"):
            _active_fixture = _format_football_fixture(data["response"][0])
            _cached_fixture_data = data["response"][0]
            _cache_timestamp = time.time()

    elif sport == "basketball":
        base = SPORT_CONFIGS["basketball"]["base_url"]
        data = _api_sports_request(base, "/games", {"id": str(fixture_id)})
        if data and data.get("response"):
            _active_fixture = _format_basketball_game(data["response"][0])
            _cached_fixture_data = data["response"][0]
            _cache_timestamp = time.time()

    elif sport == "cricket":
        data = _cricket_api_request("/match_info", {"id": str(fixture_id)})
        if data and data.get("data"):
            formatted = _format_cricket_match(data["data"])
            if formatted:
                _active_fixture = formatted
                _cached_fixture_data = data["data"]
                _cache_timestamp = time.time()

    return _active_fixture


# ── Venue Layout Builder ─────────────────────────────────────────────────────

# Well-known venue→zone mapping for popular stadiums
_VENUE_ZONE_OVERRIDES: dict = {
    # Football
    "wembley": {
        "zones": ["Wembley Way End", "Bobby Moore Stand", "Olympic Gallery", "Club Wembley"],
        "gates": ["Gate A (North)", "Gate B (South)", "Gate C (East)", "Gate D (West)"],
    },
    "old trafford": {
        "zones": ["Sir Alex Ferguson Stand", "Stretford End", "East Stand", "West Stand Lower"],
        "gates": ["Munich Tunnel Gate", "Stretford Gate", "East Gate", "West Gate"],
    },
    "anfield": {
        "zones": ["Kop Stand", "Anfield Road End", "Main Stand", "Centenary Stand"],
        "gates": ["Gate 1 (Kop)", "Gate 2 (Anfield Road)", "Gate 3 (Main)", "Gate 4 (Centenary)"],
    },
    "camp nou": {
        "zones": ["Tribuna Nord", "Tribuna Sud", "Tribuna Est", "Tribuna Oest"],
        "gates": ["Gate 14 (Norte)", "Gate 26 (Sur)", "Gate 5 (Este)", "Gate 1 (Oeste)"],
    },
    "san siro": {
        "zones": ["Curva Nord", "Curva Sud", "Tribuna Rossa", "Tribuna Blu"],
        "gates": ["Gate 1 (Nord)", "Gate 14 (Sud)", "Gate 8 (Est)", "Gate 21 (Ovest)"],
    },
    "emirates": {
        "zones": ["North Bank", "Clock End", "East Stand", "West Stand"],
        "gates": ["Gate A (North)", "Gate N (Clock)", "Gate H (East)", "Gate Q (West)"],
    },
    # Cricket
    "eden gardens": {
        "zones": ["Club House End", "B Block Pavilion", "High Court End", "D Block Gallery"],
        "gates": ["Gate 1 (Club)", "Gate 11 (Pavilion)", "Gate 21 (High Court)", "Gate 8 (Gallery)"],
    },
    "wankhede": {
        "zones": ["North Stand", "Vijay Merchant Pavilion", "Sunil Gavaskar Stand", "Garware Pavilion"],
        "gates": ["Gate 1 (North)", "Gate 3 (Pavilion)", "Gate 5 (Gavaskar)", "Gate 7 (Garware)"],
    },
    "lords": {
        "zones": ["Pavilion End", "Nursery End", "Warner Stand", "Edrich Stand"],
        "gates": ["Grace Gate (Pavilion)", "St John's Wood Gate", "East Gate", "North Gate"],
    },
    # Basketball / NBA
    "crypto.com arena": {
        "zones": ["North Plaza", "South Entry", "Staples Center East", "VIP West"],
        "gates": ["Gate 1 (Figueroa)", "Gate 11 (Chick Hearn)", "Gate 4 (East)", "Gate 7 (West)"],
    },
    "madison square garden": {
        "zones": ["Section 100 (Floor)", "Section 200 (Lower Bowl)", "Section 300 (Upper Bowl)", "Section 400 (Suite Level)"],
        "gates": ["33rd St Gate", "32nd St Gate", "7th Ave Gate", "8th Ave Gate"],
    },
    "chase center": {
        "zones": ["North Club", "South Plaza", "East View", "West Premium"],
        "gates": ["Gate A (Third St)", "Gate C (Terry Francois)", "Gate D (Warriors)", "Gate B (Lake)"],
    },
}

def _get_venue_zones(venue_name: str) -> tuple:
    """Return (zone_names, gate_names) for a venue, using overrides or generic fallback."""
    key = venue_name.lower().strip()
    for known, config in _VENUE_ZONE_OVERRIDES.items():
        if known in key:
            return config["zones"], config["gates"]
    # Generic fallback with venue-specific naming
    short = venue_name.split()[0] if venue_name else "Stadium"
    zones = [
        f"{short} North Stand",
        f"{short} South Stand",
        f"{short} East Stand",
        f"{short} West Stand",
    ]
    gates = ["Gate N (North)", "Gate S (South)", "Gate E (East)", "Gate W (West)"]
    return zones, gates


def build_venue_layout(venue_name: str, capacity: int = 50000) -> dict:
    """Build a venue layout with zone and gate names derived from the real venue."""
    zones_names, gate_names = _get_venue_zones(venue_name)
    short = venue_name.split()[0] if venue_name else "Stadium"

    zones = [
        {"id": "A", "name": zones_names[0], "sections": ["A1", "A2", "A3"],
         "nearest_gate": gate_names[0], "nearest_food": f"{short} Food Court A",
         "nearest_restroom": f"{short} Restroom N1"},
        {"id": "B", "name": zones_names[1], "sections": ["B1", "B2", "B3"],
         "nearest_gate": gate_names[1], "nearest_food": f"{short} Food Court B",
         "nearest_restroom": f"{short} Restroom S1"},
        {"id": "C", "name": zones_names[2], "sections": ["C1", "C2", "C3"],
         "nearest_gate": gate_names[2], "nearest_food": f"{short} Food Court C",
         "nearest_restroom": f"{short} Restroom E1"},
        {"id": "D", "name": zones_names[3], "sections": ["D1", "D2", "D3"],
         "nearest_gate": gate_names[3], "nearest_food": f"{short} Food Court D",
         "nearest_restroom": f"{short} Restroom W1"},
    ]
    gates = [
        {"id": gate_names[0], "location": "North", "status": "open"},
        {"id": gate_names[1], "location": "South", "status": "open"},
        {"id": gate_names[2], "location": "East", "status": "open"},
        {"id": gate_names[3], "location": "West", "status": "open"},
    ]
    facilities = [
        {"id": f"{short} Food Court A", "zone": "A", "type": "food"},
        {"id": f"{short} Food Court B", "zone": "B", "type": "food"},
        {"id": f"{short} Food Court C", "zone": "C", "type": "food"},
        {"id": f"{short} Food Court D", "zone": "D", "type": "food"},
        {"id": f"{short} Restroom N1", "zone": "A", "type": "restroom"},
        {"id": f"{short} Restroom S1", "zone": "B", "type": "restroom"},
        {"id": f"{short} Restroom E1", "zone": "C", "type": "restroom"},
        {"id": f"{short} Restroom W1", "zone": "D", "type": "restroom"},
        {"id": f"{short} First Aid North", "zone": "A", "type": "medical"},
        {"id": f"{short} First Aid South", "zone": "B", "type": "medical"},
    ]
    return {
        "venue_name": venue_name,
        "total_capacity": capacity,
        "zones": zones,
        "gates": gates,
        "facilities": facilities,
    }


# ── Dynamic Crowd & Queue Simulation ─────────────────────────────────────────

def _seed_for_cycle() -> int:
    """Generate a seed that changes every 30 seconds."""
    return int(time.time() // 30)


def simulate_crowd_data(fixture: Optional[dict] = None) -> dict:
    """Dynamically simulate crowd density and queue times based on match state.

    Sport-aware: uses the correct phase detection for each sport.
    """
    seed = _seed_for_cycle()
    sport = fixture.get("sport", _active_sport) if fixture else _active_sport

    # Determine phase using sport-specific logic
    if sport == "basketball":
        phase = _basketball_phase(fixture)
    elif sport == "cricket":
        phase = _cricket_phase(fixture)
    else:
        phase = _football_phase(fixture)

    phase_params = {
        "pre_match":    {"density": (20, 50), "food": (2, 6),  "restroom": (1, 4)},
        "first_half":   {"density": (40, 70), "food": (3, 8),  "restroom": (2, 5)},
        "halftime":     {"density": (35, 55), "food": (8, 18), "restroom": (6, 14)},
        "second_half":  {"density": (50, 80), "food": (3, 7),  "restroom": (2, 5)},
        "final_10":     {"density": (60, 90), "food": (2, 5),  "restroom": (1, 4)},
        "extra_time":   {"density": (55, 85), "food": (3, 6),  "restroom": (2, 4)},
        "post_match":   {"density": (70, 95), "food": (1, 3),  "restroom": (1, 3)},
    }
    params = phase_params.get(phase, phase_params["pre_match"])

    zone_configs = [("A", "North Stand"), ("B", "South Stand"),
                    ("C", "East Stand"), ("D", "West Stand")]
    zone_density = []
    for zone_id, zone_name in zone_configs:
        zone_seed = hashlib.md5(f"{seed}{zone_id}".encode()).hexdigest()
        zone_rng = random.Random(int(zone_seed, 16))
        density = zone_rng.randint(params["density"][0], params["density"][1])
        level = "low" if density < 40 else "medium" if density <= 70 else "high"
        zone_density.append({
            "zone_id": zone_id, "zone_name": zone_name,
            "density_percent": density, "level": level,
        })

    queues = []
    for fid in ["Food Court A", "Food Court B", "Food Court C", "Food Court D"]:
        fac_seed = hashlib.md5(f"{seed}{fid}".encode()).hexdigest()
        fac_rng = random.Random(int(fac_seed, 16))
        wait = fac_rng.randint(params["food"][0], params["food"][1])
        crowd_pct = min(95, max(10, wait * 8 + fac_rng.randint(-5, 10)))
        level = "low" if wait < 5 else "medium" if wait <= 10 else "high"
        queues.append({"facility_id": fid, "wait_minutes": wait,
                       "crowd_level": level, "crowd_percent": crowd_pct})

    for fid in ["Restroom N1", "Restroom S1", "Restroom E1", "Restroom W1"]:
        fac_seed = hashlib.md5(f"{seed}{fid}".encode()).hexdigest()
        fac_rng = random.Random(int(fac_seed, 16))
        wait = fac_rng.randint(params["restroom"][0], params["restroom"][1])
        crowd_pct = min(95, max(10, wait * 10 + fac_rng.randint(-5, 10)))
        level = "low" if wait < 5 else "medium" if wait <= 10 else "high"
        queues.append({"facility_id": fid, "wait_minutes": wait,
                       "crowd_level": level, "crowd_percent": crowd_pct})

    return {
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "queues": queues, "zone_density": zone_density,
    }


# ── Live Game State ──────────────────────────────────────────────────────────

def get_live_game_state() -> Optional[dict]:
    """Build a sport-aware game state dict from the active fixture."""
    fixture = refresh_live_fixture()
    if not fixture:
        return None

    sport = fixture.get("sport", _active_sport)

    # Get sport-specific state
    if sport == "basketball":
        sport_state = _basketball_game_state(fixture)
    elif sport == "cricket":
        sport_state = _cricket_game_state(fixture)
    else:
        sport_state = _football_game_state(fixture)

    status_display = "live" if fixture.get("is_live") else "scheduled"
    if sport_state.get("post_match_exit_open"):
        status_display = "finished"

    return {
        "event_name": f"{fixture['home_team']} vs {fixture['away_team']}",
        "league": fixture.get("league", ""),
        "sport": SPORT_CONFIGS.get(sport, {}).get("label", sport.title()),
        "status": status_display,
        "home_logo": fixture.get("home_logo", ""),
        "away_logo": fixture.get("away_logo", ""),
        "score": {
            "home": str(fixture.get("score_home", 0) or 0),
            "away": str(fixture.get("score_away", 0) or 0),
            "home_team": fixture["home_team"],
            "away_team": fixture["away_team"],
        },
        "venue_name": fixture.get("venue_name", "Unknown Venue"),
        **sport_state,
    }


def is_live_mode() -> bool:
    """Check if a live match is currently active."""
    return _active_fixture is not None
