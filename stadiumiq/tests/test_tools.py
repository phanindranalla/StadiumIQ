"""
Unit tests for StadiumIQ tools module.

Tests all 5 tool functions using mocked live_data calls so tests
don't depend on actual API or data files.
"""

import json
import unittest
from unittest.mock import patch, MagicMock

from tools import (
    get_crowd_density,
    get_queue_times,
    get_best_facility,
    get_exit_strategy,
    get_game_state,
)


# ── Mock Data ────────────────────────────────────────────────────────────────

MOCK_QUEUE_DATA = {
    "last_updated": "2025-04-20T14:30:00",
    "queues": [
        {"facility_id": "Food Court A", "wait_minutes": 4, "crowd_level": "low", "crowd_percent": 30},
        {"facility_id": "Food Court B", "wait_minutes": 12, "crowd_level": "high", "crowd_percent": 85},
        {"facility_id": "Food Court C", "wait_minutes": 6, "crowd_level": "medium", "crowd_percent": 55},
        {"facility_id": "Food Court D", "wait_minutes": 3, "crowd_level": "low", "crowd_percent": 25},
        {"facility_id": "Restroom N1", "wait_minutes": 2, "crowd_level": "low", "crowd_percent": 20},
        {"facility_id": "Restroom S1", "wait_minutes": 8, "crowd_level": "high", "crowd_percent": 80},
        {"facility_id": "Restroom E1", "wait_minutes": 3, "crowd_level": "low", "crowd_percent": 30},
        {"facility_id": "Restroom W1", "wait_minutes": 5, "crowd_level": "medium", "crowd_percent": 50},
    ],
    "zone_density": [
        {"zone_id": "A", "zone_name": "North Stand", "density_percent": 45, "level": "medium"},
        {"zone_id": "B", "zone_name": "South Stand", "density_percent": 88, "level": "high"},
        {"zone_id": "C", "zone_name": "East Stand", "density_percent": 30, "level": "low"},
        {"zone_id": "D", "zone_name": "West Stand", "density_percent": 60, "level": "medium"},
    ],
}

MOCK_VENUE = {
    "venue_name": "Old Trafford",
    "total_capacity": 74310,
    "zones": [
        {"id": "A", "name": "North Stand", "sections": ["A1", "A2", "A3"],
         "nearest_gate": "Gate 1", "nearest_food": "Food Court A", "nearest_restroom": "Restroom N1"},
        {"id": "B", "name": "South Stand", "sections": ["B1", "B2", "B3"],
         "nearest_gate": "Gate 2", "nearest_food": "Food Court B", "nearest_restroom": "Restroom S1"},
        {"id": "C", "name": "East Stand", "sections": ["C1", "C2", "C3"],
         "nearest_gate": "Gate 3", "nearest_food": "Food Court C", "nearest_restroom": "Restroom E1"},
        {"id": "D", "name": "West Stand", "sections": ["D1", "D2", "D3"],
         "nearest_gate": "Gate 4", "nearest_food": "Food Court D", "nearest_restroom": "Restroom W1"},
    ],
    "gates": [
        {"id": "Gate 1", "location": "North", "status": "open"},
        {"id": "Gate 2", "location": "South", "status": "open"},
        {"id": "Gate 3", "location": "East", "status": "open"},
        {"id": "Gate 4", "location": "West", "status": "open"},
    ],
    "facilities": [],
}

MOCK_GAME_STATE = {
    "event_name": "Man United vs Liverpool",
    "sport": "Football",
    "status": "live",
    "period": "Second Half",
    "time_remaining_minutes": 34,
    "score": {"home": "2", "away": "1", "home_team": "Man United", "away_team": "Liverpool"},
    "is_halftime": False,
    "is_final_10_minutes": False,
    "estimated_end_time": "16:15",
    "post_match_exit_open": False,
}

MOCK_GAME_STATE_HALFTIME = {**MOCK_GAME_STATE, "is_halftime": True, "period": "Half-Time"}
MOCK_GAME_STATE_FINAL_10 = {**MOCK_GAME_STATE, "is_final_10_minutes": True, "time_remaining_minutes": 8}
MOCK_GAME_STATE_NEARING_END = {**MOCK_GAME_STATE, "time_remaining_minutes": 20}


# ── Helper: mock tools internals ─────────────────────────────────────────────

def _patch_tools_data(venue=None, queue=None, game=None, live_mode=False):
    """Create a set of patches for tools.py internal helpers.

    This patches _get_venue_data, _get_queue_data, and the live_data functions
    used by tools.py to return our mock data.
    """
    patches = {
        "tools.is_live_mode": patch("tools.is_live_mode", return_value=live_mode),
        "tools.get_active_venue": patch("tools.get_active_venue", return_value=venue),
        "tools.get_active_match": patch("tools.get_active_match", return_value=None),
        "tools.simulate_crowd_data": patch("tools.simulate_crowd_data", return_value=queue),
        "tools.get_live_game_state": patch("tools.get_live_game_state", return_value=game),
        "tools.refresh_live_fixture": patch("tools.refresh_live_fixture", return_value=None),
    }
    return patches


# ── Test Classes ─────────────────────────────────────────────────────────────

class TestGetCrowdDensity(unittest.TestCase):
    """Tests for get_crowd_density()."""

    @patch("tools._get_queue_data")
    def test_returns_sorted_zones_descending(self, mock_queue):
        """Zones should be sorted by density_percent in descending order."""
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_crowd_density()
        densities = [z["density_percent"] for z in result["zones"]]
        self.assertEqual(densities, sorted(densities, reverse=True))

    @patch("tools._get_queue_data")
    def test_identifies_most_and_least_crowded(self, mock_queue):
        """Should correctly identify the most and least crowded zones."""
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_crowd_density()
        self.assertEqual(result["most_crowded"], "South Stand")
        self.assertEqual(result["least_crowded"], "East Stand")

    @patch("tools._get_queue_data")
    def test_handles_error(self, mock_queue):
        """Should return error dict when data source is unavailable."""
        mock_queue.return_value = {"error": "Data not found"}
        result = get_crowd_density()
        self.assertIn("error", result)


class TestGetQueueTimes(unittest.TestCase):
    """Tests for get_queue_times()."""

    @patch("tools._get_queue_data")
    def test_returns_all_queues_sorted(self, mock_queue):
        """All queues should be returned sorted by wait_minutes ascending."""
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_queue_times("all")
        wait_times = [q["wait_minutes"] for q in result]
        self.assertEqual(wait_times, sorted(wait_times))
        self.assertEqual(len(result), 8)

    @patch("tools._get_queue_data")
    def test_filters_food_only(self, mock_queue):
        """Should return only food court facilities when filtered."""
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_queue_times("food")
        self.assertTrue(all("Food Court" in q["facility_id"] for q in result))
        self.assertEqual(len(result), 4)

    @patch("tools._get_queue_data")
    def test_filters_restroom_only(self, mock_queue):
        """Should return only restroom facilities when filtered."""
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_queue_times("restroom")
        self.assertTrue(all("Restroom" in q["facility_id"] for q in result))
        self.assertEqual(len(result), 4)

    @patch("tools._get_queue_data")
    def test_handles_error(self, mock_queue):
        """Should return a list with error dict when data is unavailable."""
        mock_queue.return_value = {"error": "Data not found"}
        result = get_queue_times()
        self.assertIsInstance(result, list)
        self.assertIn("error", result[0])


class TestGetBestFacility(unittest.TestCase):
    """Tests for get_best_facility()."""

    @patch("tools._get_queue_data")
    @patch("tools._get_venue_data")
    def test_finds_nearest_food_for_zone_a(self, mock_venue, mock_queue):
        """Should find Food Court A for zone A with correct queue data."""
        mock_venue.return_value = MOCK_VENUE
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_best_facility("A", "food")
        self.assertEqual(result["facility_name"], "Food Court A")
        self.assertEqual(result["wait_minutes"], 4)
        self.assertEqual(result["crowd_level"], "low")
        self.assertEqual(result["walk_minutes"], 2)

    @patch("tools._get_queue_data")
    @patch("tools._get_venue_data")
    def test_finds_nearest_restroom_for_zone_b(self, mock_venue, mock_queue):
        """Should find Restroom S1 for zone B with high crowd walk time."""
        mock_venue.return_value = MOCK_VENUE
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_best_facility("B", "restroom")
        self.assertEqual(result["facility_name"], "Restroom S1")
        self.assertEqual(result["wait_minutes"], 8)
        self.assertEqual(result["crowd_level"], "high")
        self.assertEqual(result["walk_minutes"], 6)

    @patch("tools._get_queue_data")
    @patch("tools._get_venue_data")
    def test_invalid_zone_returns_error(self, mock_venue, mock_queue):
        """Should return an error dict for an invalid zone."""
        mock_venue.return_value = MOCK_VENUE
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_best_facility("Z", "food")
        self.assertIn("error", result)

    @patch("tools._get_venue_data")
    def test_handles_venue_error(self, mock_venue):
        """Should return an error dict when venue data is unavailable."""
        mock_venue.return_value = {"error": "Venue not found"}
        result = get_best_facility("A", "food")
        self.assertIn("error", result)


class TestGetExitStrategy(unittest.TestCase):
    """Tests for get_exit_strategy()."""

    @patch("tools._get_queue_data")
    @patch("tools._get_venue_data")
    def test_low_density_zone(self, mock_venue, mock_queue):
        """Zone C (East Stand) has 30% density — should return 5 min wait."""
        mock_venue.return_value = MOCK_VENUE
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_exit_strategy("C1")
        self.assertEqual(result["recommended_gate"], "Gate 3")
        self.assertEqual(result["zone_name"], "East Stand")
        self.assertEqual(result["estimated_wait"], "5 mins")
        self.assertIn("tip", result)

    @patch("tools._get_queue_data")
    @patch("tools._get_venue_data")
    def test_high_density_zone(self, mock_venue, mock_queue):
        """Zone B (South Stand) has 88% density — should return 18 min wait."""
        mock_venue.return_value = MOCK_VENUE
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_exit_strategy("B2")
        self.assertEqual(result["recommended_gate"], "Gate 2")
        self.assertEqual(result["zone_name"], "South Stand")
        self.assertEqual(result["estimated_wait"], "18 mins")

    @patch("tools._get_queue_data")
    @patch("tools._get_venue_data")
    def test_medium_density_zone(self, mock_venue, mock_queue):
        """Zone A (North Stand) has 45% density — should return 10 min wait."""
        mock_venue.return_value = MOCK_VENUE
        mock_queue.return_value = MOCK_QUEUE_DATA
        result = get_exit_strategy("A1")
        self.assertEqual(result["estimated_wait"], "10 mins")

    @patch("tools._get_venue_data")
    def test_handles_venue_error(self, mock_venue):
        """Should return an error dict when venue data is unavailable."""
        mock_venue.return_value = {"error": "Venue not found"}
        result = get_exit_strategy("A1")
        self.assertIn("error", result)


class TestGetGameState(unittest.TestCase):
    """Tests for get_game_state()."""

    @patch("tools.is_live_mode", return_value=False)
    @patch("tools._load_json")
    def test_plenty_of_time_tip(self, mock_load, mock_live):
        """With 34 minutes remaining, should show 'plenty of time' tip."""
        mock_load.return_value = json.loads(json.dumps(MOCK_GAME_STATE))
        result = get_game_state()
        self.assertEqual(result["context_tip"], "Plenty of time left — enjoy the match")
        self.assertEqual(result["event_name"], "Man United vs Liverpool")

    @patch("tools.is_live_mode", return_value=False)
    @patch("tools._load_json")
    def test_halftime_tip(self, mock_load, mock_live):
        """During half-time, should show facilities tip."""
        mock_load.return_value = json.loads(json.dumps(MOCK_GAME_STATE_HALFTIME))
        result = get_game_state()
        self.assertEqual(result["context_tip"], "Half-time now — good time to visit facilities")

    @patch("tools.is_live_mode", return_value=False)
    @patch("tools._load_json")
    def test_final_10_minutes_tip(self, mock_load, mock_live):
        """In final 10 minutes, should show exit tip."""
        mock_load.return_value = json.loads(json.dumps(MOCK_GAME_STATE_FINAL_10))
        result = get_game_state()
        self.assertEqual(result["context_tip"], "Final 10 mins — consider moving to exit soon")

    @patch("tools.is_live_mode", return_value=False)
    @patch("tools._load_json")
    def test_nearing_end_tip(self, mock_load, mock_live):
        """With 20 minutes remaining, should show 'nearing end' tip."""
        mock_load.return_value = json.loads(json.dumps(MOCK_GAME_STATE_NEARING_END))
        result = get_game_state()
        self.assertEqual(result["context_tip"], "Match nearing end — plan your exit")

    @patch("tools.is_live_mode", return_value=False)
    @patch("tools._load_json", side_effect=FileNotFoundError)
    def test_handles_missing_file(self, mock_load, mock_live):
        """Should return an error dict when data file is not found."""
        result = get_game_state()
        self.assertIn("error", result)

    @patch("tools.is_live_mode", return_value=True)
    @patch("tools.get_live_game_state")
    def test_live_mode_uses_api_data(self, mock_live_state, mock_live_mode):
        """In live mode, should use API data instead of JSON files."""
        mock_live_state.return_value = {
            **MOCK_GAME_STATE,
            "event_name": "Live Match",
        }
        result = get_game_state()
        self.assertEqual(result["event_name"], "Live Match")
        self.assertIn("context_tip", result)


if __name__ == "__main__":
    unittest.main()
