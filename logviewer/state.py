# state.py

import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.expanduser("~/.logviewer_state.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS parsed_bundles (
            bundle_path TEXT PRIMARY KEY,
            output_path TEXT NOT NULL,
            port INTEGER,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_parsed_bundle(bundle_path, output_path, port=None):
    init_db()
    timestamp = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO parsed_bundles (bundle_path, output_path, port, timestamp)
        VALUES (?, ?, ?, ?)
    """, (os.path.abspath(bundle_path), output_path, port, timestamp))
    conn.commit()
    conn.close()

def remove_parsed_bundle(bundle_path):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM parsed_bundles WHERE bundle_path = ?", (os.path.abspath(bundle_path),))
    conn.commit()
    conn.close()

def get_parsed_bundles():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT bundle_path, output_path, port, timestamp FROM parsed_bundles")
    rows = c.fetchall()
    conn.close()
    return {row[0]: {"output_path": row[1], "port": row[2], "timestamp": row[3]} for row in rows}

def get_next_available_port(start_port=8001):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT port FROM parsed_bundles WHERE port IS NOT NULL")
    used_ports = {row[0] for row in c.fetchall()}
    conn.close()
    port = start_port
    while port in used_ports:
        port += 1
    return port
