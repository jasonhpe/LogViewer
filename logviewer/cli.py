
import argparse
import os
import sys
import subprocess
import webbrowser
from pathlib import Path
from logviewer import parse_bundle
from logviewer.gui import launch_gui
from logviewer.state import load_state, save_state, add_parsed_bundle, get_parsed_bundles, get_next_available_port

def analyze_bundle(bundle_path):
    if not os.path.isfile(bundle_path):
        print(f"❌ File not found: {bundle_path}")
        sys.exit(1)

    state = load_state()
    print(f"🔍 Parsing: {bundle_path}...")
    out_dir = parse_bundle(bundle_path)
    if not out_dir:
        print("❌ Parsing failed.")
        return
    port = get_next_available_port(state)
    add_parsed_bundle(state, bundle_path, out_dir, port)
    print(f"✅ Parsed output saved to: {out_dir}")
