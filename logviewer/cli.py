import argparse
import os
import sys
import subprocess
import webbrowser
import time
import socket
from pathlib import Path
from logviewer.parser import parse_bundle
from logviewer.gui import launch_gui
from logviewer.state import (
    load_state,
    save_state,
    add_parsed_bundle,
    get_parsed_bundles,
    get_next_available_port,
)

def analyze_bundle(bundle_path, open_after=False):
    if not os.path.isfile(bundle_path):
        print(f"❌ File not found: {bundle_path}")
        sys.exit(1)

    state = load_state()
    print(f"📦 Parsing: {bundle_path}...")

    output_dir = bundle_path + "_log_analysis_results"
    out_dir = parse_bundle(bundle_path, output_dir)  

    if not out_dir:
        print("❌ Parsing failed.")
        return

    port = get_next_available_port(state)
    add_parsed_bundle(state, bundle_path, out_dir, port)
    print(f"✅ Parsed output saved to: {out_dir}")

    if open_after:
        print("🔍 Launching viewer...")
        view_bundle(os.path.basename(out_dir))

def list_bundles():
    state = load_state()
    bundles = get_parsed_bundles(state)
    if not bundles:
        print("ℹ️  No parsed bundles found.")
        return

    print("📁 Parsed Bundles:")
    for idx, (src, meta) in enumerate(bundles.items(), 1):
        print(f"{idx}. {os.path.basename(src)} -> {meta['output_path']} (Port: {meta.get('port', 'Not assigned')})")

def wait_for_server(host, port, timeout=5):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    return False

def view_bundle(bundle_name):
    state = load_state()
    bundles = get_parsed_bundles(state)

    if bundle_name == "latest":
        if not bundles:
            print("❌ No parsed bundles found.")
            return
        latest_entry = max(bundles.items(), key=lambda kv: kv[1].get("timestamp", ""))
        bundle = latest_entry[1]
    else:
        matched = None
        for meta in bundles.values():
            if os.path.basename(meta["output_path"]).startswith(bundle_name):
                matched = meta
                break
        if not matched:
            print(f"❌ Bundle '{bundle_name}' not found in state.")
            return
        bundle = matched

    path = bundle["output_path"]
    port = bundle.get("port") or get_next_available_port(state)
    bundle["port"] = port
    save_state(state)

    print(f"🌐 Serving '{path}' at http://localhost:{port}")
    proc = subprocess.Popen(["python3", "-m", "http.server", str(port), "--directory", path])

    if wait_for_server("localhost", port, timeout=5):
        webbrowser.open(f"http://localhost:{port}/index.html")
        proc.wait()
    else:
        print("❌ Server failed to start in time.")
        proc.terminate()

def main():
    parser = argparse.ArgumentParser(
        description="LogViewer CLI - Analyze and view Aruba support bundles\n\n"
                    "Usage examples:\n"
                    "  LogViewer analyze --path support1.tar.gz\n"
                    "  LogViewer analyze --path support1.tar.gz --open\n"
                    "  LogViewer list\n"
                    "  LogViewer view --bundle latest\n"
                    "  LogViewer view --bundle support.files.123456",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser("analyze", help="Parse a new bundle (.tar.gz)")
    analyze.add_argument(
        "--path",
        required=True,
        metavar="PATH",
        help="Path to .tar.gz support bundle",
    )
    analyze.add_argument(
        "--open",
        action="store_true",
        help="Open parsed bundle in browser after parsing"
    )
    

    list_cmd = subparsers.add_parser("list", help="List previously parsed bundles")

    view = subparsers.add_parser("view", help="Open the log viewer for a parsed bundle")
    view.add_argument("--bundle", required=True, metavar="NAME", help="Bundle name or 'latest'")

    args = parser.parse_args()

    if args.command == "analyze":
        analyze_bundle(args.path, open_after=args.open)
    elif args.command == "list":
        list_bundles()
    elif args.command == "view":
        view_bundle(args.bundle)
    else:
        launch_gui()

if __name__ == "__main__":
    main()
