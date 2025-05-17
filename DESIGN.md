# 🧩 LogViewer Design Document

This document explains the internal design and structure of the **LogViewer** project, including its core components, file structure, and the logic behind parsing and rendering Aruba switch support bundles.

---

## 📁 Directory Structure

```markdown
LogViewer/
├── logviewer/ # Python package
│ ├── init.py
│ ├── cli.py # CLI entry point logic
│ ├── gui.py # Tkinter GUI interface
│ ├── parser.py # Bundle parsing and extraction logic
│ ├── state.py # Persistent session tracking (parsed bundles, ports, etc.)
│ ├── html_template.py # HTML viewer layout and JS logic
│
├── setup.py # setuptools configuration for CLI installation
├── README.md
├── DESIGN.md
└── .logviewer_state.json # Automatically created; tracks bundle metadata
```


---

## 🛠️ Components

### 1. `cli.py` – Command Line Interface

Implements commands:
- `LogViewer analyze --path <bundle>`: parses a support bundle
- `LogViewer list`: shows previously parsed bundles
- `LogViewer view --bundle <name|latest>`: launches HTML viewer in browser

Manages port allocation, state loading/saving, and subprocess for serving.

### 2. `gui.py` – Desktop GUI

Tkinter-based interface that allows:
- Drag-and-drop support for `.tar.gz` bundles
- Browsing parsed bundles
- Button to launch local HTML viewer

### 3. `parser.py` – Parsing & Extraction Logic

Handles:
- `.tar.gz` extraction
- `fastlog` parsing using `fastlogParser`
- Splitting `showtech.txt` into individual sections
- Organizing diagdumps into `/feature/`
- Generating indexes for fastlog, diag, and showtech tabs

### 4. `html_template.py`

Contains:
- Bootstrap-based layout for tabbed HTML view
- JavaScript for filtering logs, rendering fastlogs, diag, and showtech
- Dropdowns for each content section (fastlog, diag, showtech)

---

## 🔁 State Management

`state.py` maintains:
- A JSON database of previously parsed bundles
- The mapping of `bundle_path` → `output_dir`, timestamp, assigned port
- Used by both GUI and CLI to avoid re-parsing

Saved as:
~/.logviewer_state.json

---

## 🌐 Serving HTML

Uses Python's built-in HTTP server:
```bash
python3 -m http.server <port> --directory <output_dir>
```
This allows viewing the HTML dashboard in the browser at:

http://localhost:<port>
