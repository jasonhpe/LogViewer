import argparse
import os
import sys
import subprocess
import webbrowser
from pathlib import Path
from argparse import RawTextHelpFormatter
import time
from logviewer.parser import parse_bundle
from logviewer.gui import launch_gui
from logviewer.state import (
    load_state,
    save_state,
    add_parsed_bundle,
    get_parsed_bundles,
    get_next_available_port,
)

def analyze_bundle(bundle_path):
    if not os.path.isfile(bundle_path):
        print(f" File not found: {bundle_path}")
        sys.exit(1)

    state = load_state()
    print(f"📦 Parsing: {bundle_path}...")

    # Set default output_dir based on bundle name
    base_name = os.path.basename(bundle_path)
    out_dir = os.path.abspath(f"{base_name}_log_analysis_results")

    out_dir = parse_bundle(bundle_path, out_dir)
    if not out_dir:
        print("❌ Parsing failed.")
        return

    port = get_next_available_port(state)
    add_parsed_bundle(state, bundle_path, out_dir, port)
    print(f"✅ Parsed output saved to: {out_dir}")

def list_bundles():
    state = load_state()
    bundles = get_parsed_bundles(state)
    if not bundles:
        print("⚠️  No parsed bundles found.")
        return

    print("📂 Parsed Bundles:")
    for idx, (src, meta) in enumerate(bundles.items(), 1):
        print(f"{idx}. {os.path.basename(src)} -> {meta['output_path']} (Port: {meta.get('port', 'Not assigned')})")

def view_bundle(bundle_name):
    from pathlib import Path

    state = load_state()
    bundles = get_parsed_bundles(state)

    if not bundles:
        print("❌ No parsed bundles found.")
        return

    if bundle_name == "latest":
        # Get the latest by timestamp
        latest_entry = max(bundles.items(), key=lambda kv: kv[1].get("timestamp", ""))
        bundle = latest_entry[1]
    else:
        # Try to match by substring in bundle name
        matched = None
        for src, meta in bundles.items():
            if bundle_name in os.path.basename(meta["output_path"]):
                matched = meta
                break
        if not matched:
            print(f"❌ Bundle '{bundle_name}' not found.")
            print("👉 Use 'LogViewer list' to see available bundles.")
            return
        bundle = matched

    path = bundle["output_path"]
    port = bundle.get("port") or get_next_available_port(state)
    bundle["port"] = port
    save_state(state)

    index_path = os.path.join(path, "index.html")
    if not os.path.isfile(index_path):
        print(f"❌ index.html not found in {path}")
        print("📌 Make sure this bundle was parsed successfully.")
        return

    print(f"🌐 Serving '{path}' at http://localhost:{port}")
    webbrowser.open(f"http://localhost:{port}/index.html")
    subprocess.run(["python3", "-m", "http.server", str(port), "--directory", path])

def main():
    parser = argparse.ArgumentParser(
        description=(
            "LogViewer CLI - Analyze and view Aruba support bundles\n\n"
            "Usage examples:\n"
            "  LogViewer analyze --path support1.tar.gz\n"
            "  LogViewer list\n"
            "  LogViewer view --bundle latest\n"
            "  LogViewer view --bundle <parsed bundle>\n"
        ),
        formatter_class=RawTextHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Parse a new bundle (.tar.gz)")
    analyze.add_argument(
        "--path",
        required=True,
        metavar="PATH",
        help="Full path to the .tar.gz support bundle (example: --path support1.tar.gz)"
    )

    list_cmd = subparsers.add_parser("list", help="List previously parsed bundles")

    view = subparsers.add_parser("view", help="Open the log viewer for a parsed bundle")
    view.add_argument(
        "--bundle",
        required=True,
        metavar="NAME",
        help="Bundle name to view (use --bundle latest to view most recent)"
    )

    args = parser.parse_args()
    cmd = args.command

    if cmd == "analyze":
        analyze_bundle(args.path)
    elif cmd == "list":
        list_bundles()
    elif cmd == "view":
        view_bundle(args.bundle)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
