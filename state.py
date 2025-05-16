# state.py

import os
import json

STATE_FILE = os.path.expanduser("~/.logviewer_state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load state: {e}")
            return {}
    return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save state: {e}")

def add_parsed_bundle(state, bundle_path, output_path, port=None):
    state.setdefault("parsed_bundles", {})
    state["parsed_bundles"][bundle_path] = {
        "output_path": output_path,
        "port": port,
        "timestamp": __import__("datetime").datetime.now().isoformat()
    }
    save_state(state)

def remove_parsed_bundle(state, bundle_path):
    if "parsed_bundles" in state and bundle_path in state["parsed_bundles"]:
        del state["parsed_bundles"][bundle_path]
        save_state(state)

def get_parsed_bundles(state):
    return state.get("parsed_bundles", {})

def get_next_available_port(state, start_port=8001):
    used_ports = {v["port"] for v in state.get("parsed_bundles", {}).values() if v.get("port")}
    port = start_port
    while port in used_ports:
        port += 1
    return port
