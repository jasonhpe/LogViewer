# utils.py

import os
import re
from datetime import datetime

def ensure_dir(path):
    """Create directory if it doesn't exist."""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"❌ Failed to create directory {path}: {e}")

def is_tar_gz(filename):
    """Check if a file is a .tar.gz archive."""
    return filename.endswith(".tar.gz") and os.path.isfile(filename)

def sanitize_filename(name):
    """Sanitize a filename to be safe for saving."""
    return re.sub(r"[^\w\-_.]", "_", name)

def format_timestamp(ts=None):
    """Return a human-readable timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S") if ts is None else datetime.fromisoformat(ts).strftime("%Y%m%d_%H%M%S")

def find_tar_gz_files(directory):
    """Recursively find .tar.gz files in a directory."""
    result = []
    for root, _, files in os.walk(directory):
        for file in files:
            if is_tar_gz(file):
                result.append(os.path.join(root, file))
    return result
