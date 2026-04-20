"""
StadiumIQ Tools Module

Data retrieval and logic functions for venue intelligence.
When a live match is active (via live_data module), data comes from the
API-Football API with dynamically simulated crowd/queue data.
Falls back to static JSON files when no live match is selected.
"""

import json
import os
from typing import Dict, List, Optional, Union

from live_data import (
    is_live_mode,
    get_active_venue,
    get_active_match,
    simulate_crowd_data,
    get_live_game_state,
    refresh_live_fixture,
)

# Base path for data files (relative to the module location)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load_json(filename: str) -> dict:
    """Load and parse a JSON file from the data directory.

    Args:
        filename: Name of the JSON file to load.

    Returns:
        Parsed JSON data as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_venue_data() -> dict:
    """Get venue data from live source or static JSON.

    Returns:
        Venue layout dict.
    """
    if is_live_mode():
        venue = get_active_venue()
        if venue:
            return venue
    try:
        return _load_json("venue.json")
    except FileNotFoundError:
        return {"error": "Venue data not found."}


def _get_queue_data() -> dict:
    """Get crowd/queue data from live simulation or static JSON.

    Returns:
        Queue times dict with queues and zone_density.
    """
    if is_live_mode():
        fixture = get_active_match()
        return simulate_crowd_data(fixture)
    try:
        return _load_json("queue_times.json")
    except FileNotFoundError:
        return {"error": "Queue times data not found."}


def get_crowd_density() -> Dict[str, Union[List[dict], str]]:
    """Get current crowd density for all zones, sorted by density descending.

    When a live match is active, density is dynamically simulated based on
    match state (halftime, final 10 min, etc.). Falls back to static data.

    Returns:
        A dict with keys:
        - "zones": list of zone density entries sorted by density_percent descending
        - "most_crowded": name of the most crowded zone
        - "least_crowded": name of the least crowded zone
        If the data source is unavailable, returns an error dict.
    """
    data = _get_queue_data()
    if "error" in data:
        return {"error": data["error"]}

    zones = sorted(data["zone_density"], key=lambda z: z["density_percent"], reverse=True)

    return {
        "zones": zones,
        "most_crowded": zones[0]["zone_name"] if zones else "Unknown",
        "least_crowded": zones[-1]["zone_name"] if zones else "Unknown",
    }


def get_queue_times(facility_type: str = "all") -> List[dict]:
    """Get current queue wait times, optionally filtered by facility type.

    When live, queue times are simulated based on match phase (e.g., food
    queues spike at halftime). Falls back to static data.

    Args:
        facility_type: One of "food", "restroom", or "all".
            - "food" filters to facilities with "Food Court" in their ID.
            - "restroom" filters to facilities with "Restroom" in their ID.
            - "all" returns all facilities.

    Returns:
        List of queue dicts, each containing:
        facility_id, wait_minutes, crowd_level, crowd_percent.
        Sorted by wait_minutes ascending.
        If the data source is unavailable, returns a list with a single error dict.
    """
    data = _get_queue_data()
    if "error" in data:
        return [{"error": data["error"]}]

    queues = data["queues"]

    if facility_type == "food":
        queues = [q for q in queues if "Food Court" in q["facility_id"]]
    elif facility_type == "restroom":
        queues = [q for q in queues if "Restroom" in q["facility_id"]]

    return sorted(queues, key=lambda q: q["wait_minutes"])


def get_best_facility(zone_id: str, facility_type: str) -> Dict[str, Union[str, int]]:
    """Find the best (nearest) facility of a given type for a specific zone.

    Uses live venue data when available, or falls back to static JSON.

    Args:
        zone_id: The zone identifier (e.g., "A", "B", "C", "D").
        facility_type: The type of facility to find ("food" or "restroom").

    Returns:
        A dict with keys:
        - "facility_name": name/ID of the nearest facility
        - "wait_minutes": current wait time in minutes
        - "crowd_level": current crowd level (low/medium/high)
        - "walk_minutes": estimated walk time based on crowd level
          (low=2, medium=4, high=6)
        If data is unavailable, returns an error dict.
    """
    venue = _get_venue_data()
    if "error" in venue:
        return {"error": venue["error"]}

    queue_data = _get_queue_data()
    if "error" in queue_data:
        return {"error": queue_data["error"]}

    # Find the zone
    zone = None
    for z in venue["zones"]:
        if z["id"] == zone_id.upper():
            zone = z
            break

    if not zone:
        return {"error": f"Zone '{zone_id}' not found."}

    # Find the nearest facility of the requested type
    if facility_type == "food":
        facility_name = zone["nearest_food"]
    elif facility_type == "restroom":
        facility_name = zone["nearest_restroom"]
    else:
        return {"error": f"Unknown facility type: '{facility_type}'. Use 'food' or 'restroom'."}

    # Look up queue time for that facility
    queue_info = None
    for q in queue_data["queues"]:
        if q["facility_id"] == facility_name:
            queue_info = q
            break

    if not queue_info:
        return {
            "facility_name": facility_name,
            "wait_minutes": 0,
            "crowd_level": "unknown",
            "walk_minutes": 2,
        }

    # Walk time based on crowd level
    walk_minutes_map = {"low": 2, "medium": 4, "high": 6}
    walk_minutes = walk_minutes_map.get(queue_info["crowd_level"], 4)

    return {
        "facility_name": facility_name,
        "wait_minutes": queue_info["wait_minutes"],
        "crowd_level": queue_info["crowd_level"],
        "walk_minutes": walk_minutes,
    }


def get_exit_strategy(section: str) -> Dict[str, str]:
    """Get recommended exit strategy for a given seat section.

    Determines the zone from the section's first letter, finds the nearest
    gate, and estimates exit wait time based on zone density.

    Args:
        section: The seat section identifier (e.g., "A1", "B2", "C3", "D1").
            The first letter determines the zone:
            A = North Stand, B = South Stand, C = East Stand, D = West Stand.

    Returns:
        A dict with keys:
        - "recommended_gate": the nearest gate for the section's zone
        - "zone_name": the name of the zone
        - "estimated_wait": estimated exit wait time as a string
        - "tip": a short plain text advice string
        If data is unavailable, returns an error dict.
    """
    venue = _get_venue_data()
    if "error" in venue:
        return {"error": venue["error"]}

    queue_data = _get_queue_data()
    if "error" in queue_data:
        return {"error": queue_data["error"]}

    # Determine zone from section's first letter
    zone_letter = section[0].upper() if section else ""

    # Find the zone
    zone = None
    for z in venue["zones"]:
        if z["id"] == zone_letter:
            zone = z
            break

    if not zone:
        return {"error": f"Could not determine zone for section '{section}'."}

    # Find zone density
    zone_density = None
    for zd in queue_data["zone_density"]:
        if zd["zone_id"] == zone_letter:
            zone_density = zd
            break

    density_percent = zone_density["density_percent"] if zone_density else 50

    # Estimate exit wait based on density
    if density_percent < 40:
        estimated_wait = "5 mins"
        tip = "Low crowd density — you should have a smooth exit."
    elif density_percent <= 70:
        estimated_wait = "10 mins"
        tip = "Moderate crowd — consider leaving a few minutes before the final whistle."
    else:
        estimated_wait = "18 mins"
        tip = "High crowd density — leave early or wait 15 minutes after the match to avoid the rush."

    return {
        "recommended_gate": zone["nearest_gate"],
        "zone_name": zone["name"],
        "estimated_wait": estimated_wait,
        "tip": tip,
    }


def get_game_state() -> dict:
    """Get the current game/match state with a computed context tip.

    When a live match is active, returns real-time score and status from
    the API. Falls back to static game_state.json.

    Returns:
        The full game state dict with an added "context_tip" field:
        - If is_halftime: "Half-time now — good time to visit facilities"
        - If is_final_10_minutes: "Final 10 mins — consider moving to exit soon"
        - If time_remaining_minutes > 30: "Plenty of time left — enjoy the match"
        - Otherwise: "Match nearing end — plan your exit"
        If the data source is unavailable, returns an error dict.
    """
    # Try live data first
    if is_live_mode():
        live_state = get_live_game_state()
        if live_state:
            # Add context tip
            if live_state.get("is_halftime"):
                live_state["context_tip"] = "Half-time now — good time to visit facilities"
            elif live_state.get("is_final_10_minutes"):
                live_state["context_tip"] = "Final 10 mins — consider moving to exit soon"
            elif live_state.get("time_remaining_minutes", 0) > 30:
                live_state["context_tip"] = "Plenty of time left — enjoy the match"
            else:
                live_state["context_tip"] = "Match nearing end — plan your exit"
            return live_state

    # Fallback to static JSON
    try:
        data = _load_json("game_state.json")
    except FileNotFoundError:
        return {"error": "Game state data file not found."}

    # Compute context tip
    if data.get("is_halftime"):
        data["context_tip"] = "Half-time now — good time to visit facilities"
    elif data.get("is_final_10_minutes"):
        data["context_tip"] = "Final 10 mins — consider moving to exit soon"
    elif data.get("time_remaining_minutes", 0) > 30:
        data["context_tip"] = "Plenty of time left — enjoy the match"
    else:
        data["context_tip"] = "Match nearing end — plan your exit"

    return data


def get_venue_name() -> str:
    """Get the current venue name.

    Returns:
        The venue name string — either from the live match or static data.
    """
    if is_live_mode():
        venue = get_active_venue()
        if venue:
            return venue.get("venue_name", "StadiumIQ Arena")
    try:
        data = _load_json("venue.json")
        return data.get("venue_name", "StadiumIQ Arena")
    except FileNotFoundError:
        return "StadiumIQ Arena"
