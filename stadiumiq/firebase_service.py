import os
import json
import firebase_admin
from firebase_admin import credentials, db
from typing import Dict, List, Optional, Union

# Initialize Firebase
firebase_app = None
firebase_db = None

def init_firebase():
    """Initialize Firebase app using environment variables."""
    global firebase_app, firebase_db
    
    if firebase_app:
        return firebase_app

    credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON", "").strip()
    database_url = os.getenv("FIREBASE_DB_URL", "").strip()

    if not credentials_json or not database_url:
        print("Firebase configuration (FIREBASE_CREDENTIALS_JSON or FIREBASE_DB_URL) missing. Falling back to local files.")
        return None

    try:
        # Load credentials from JSON string
        cred_dict = json.loads(credentials_json)
        cred = credentials.Certificate(cred_dict)
        
        firebase_app = firebase_admin.initialize_app(cred, {
            'databaseURL': database_url
        })
        firebase_db = db
        print("Firebase initialized successfully.")
        return firebase_app
    except Exception as e:
        print(f"Error initializing Firebase: {e}. Falling back to local files.")
        return None

# Fallback loaders (mirrors tools.py logic)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def _load_local_json(filename: str) -> dict:
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": f"File {filename} not found."}

def get_queue_times_firebase() -> List[dict]:
    """Reads queue times from Firebase with local fallback."""
    if init_firebase():
        try:
            ref = db.reference('/stadiumiq/queue_times')
            data = ref.get()
            if data:
                return data
        except Exception as e:
            print(f"Firebase error in get_queue_times: {e}")
    
    # Fallback
    data = _load_local_json("queue_times.json")
    if "error" in data:
        return [{"error": data["error"]}]
    return data.get("queues", [])

def get_crowd_density_firebase() -> Dict[str, Union[List[dict], str]]:
    """Reads crowd density from Firebase with local fallback."""
    if init_firebase():
        try:
            ref = db.reference('/stadiumiq/zone_density')
            data = ref.get()
            if data:
                # Reconstruct the expected structure
                zones = sorted(data, key=lambda z: z["density_percent"], reverse=True)
                return {
                    "zones": zones,
                    "most_crowded": zones[0]["zone_name"] if zones else "Unknown",
                    "least_crowded": zones[-1]["zone_name"] if zones else "Unknown",
                }
        except Exception as e:
            print(f"Firebase error in get_crowd_density: {e}")

    # Fallback
    data = _load_local_json("queue_times.json") # tools.py uses queue_times.json for zone_density
    if "error" in data:
        return {"error": data["error"]}
    
    zones = sorted(data.get("zone_density", []), key=lambda z: z["density_percent"], reverse=True)
    return {
        "zones": zones,
        "most_crowded": zones[0]["zone_name"] if zones else "Unknown",
        "least_crowded": zones[-1]["zone_name"] if zones else "Unknown",
    }

def get_game_state_firebase() -> dict:
    """Reads game state from Firebase with local fallback."""
    if init_firebase():
        try:
            ref = db.reference('/stadiumiq/game_state')
            data = ref.get()
            if data:
                return data
        except Exception as e:
            print(f"Firebase error in get_game_state: {e}")

    # Fallback
    data = _load_local_json("game_state.json")
    if "error" in data:
        return data
        
    return data

def initialize_firebase_with_mock_data():
    """Seeds Firebase with mock data from local files."""
    if not init_firebase():
        return

    print("Seeding Firebase with mock data...")
    try:
        # 1. Queue Times & Zone Density
        queue_data = _load_local_json("queue_times.json")
        if "error" not in queue_data:
            db.reference('/stadiumiq/queue_times').set(queue_data.get("queues", []))
            db.reference('/stadiumiq/zone_density').set(queue_data.get("zone_density", []))
            print("Seeded queue_times and zone_density.")

        # 2. Game State
        game_state = _load_local_json("game_state.json")
        if "error" not in game_state:
            db.reference('/stadiumiq/game_state').set(game_state)
            print("Seeded game_state.")
            
        print("Firebase seeding complete.")
    except Exception as e:
        print(f"Error seeding Firebase: {e}")
