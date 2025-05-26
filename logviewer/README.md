# LogViewer — Aruba Log Parser & Visualizer

**LogViewer** is a Python-based GUI + CLI application to parse and visualize support bundles collected from **Aruba CX switches**. It handles `.tar.gz` support files, parses event/critical logs, `.supportlog` files (via `fastlogParser`), and generates a browsable **HTML dashboard** with filters, tabs, and a multi-bundle carousel view.

---

## 🚀 Features

- Parse .tar.gz Aruba support bundles (including VSF members, linecards, and previous boots)
- Supports logs: event.log, critical.log, journalctl, .supportlog
- Fastlog processing via fastlogParser
- Extracts and organizes:
  - Logs (merged and normalized)
  - Fastlogs (raw + merged)
  - ISP output
  - diagdump.txt
  - Sectioned showtech.txt

Interactive Streamlit-based log viewer with:
 - Tabs for Logs, Fastlogs, Diag Dumps, and ShowTech
 - Carousel navigation for multiple bundles
 - Toggleable fastlog, VSF, previous boot, and linecard parsing
 - Error timeline visualization (LOG_ERR per hour)
 - Keyword, process name, and timestamp filters
 
 Modern GUI built with Tkinter:
 - Drag-and-drop .tar.gz support
 - Persistent session state
 - Debug panel with live background task updates
 - Streamlit viewer launch controls (Start/Stop)

- CLI mode for automation and headless environments

-Fully self-contained parsing 

- All timestamps normalized in UTC

---

## 🔧 Installation

### 🪟 Windows Users – WSL Required for Fastlog Parsing
To parse `.supportlog` files on Windows, you must have **WSL (Windows Subsystem for Linux)** installed.

#### 📥 Install WSL (once)
Run the following command in **PowerShell as Administrator**:
```powershell
wsl --install
```
Then reboot the PC/Laptop for changes to take effect.

Current versions being posted at:

https://confluence.arubanetworks.com/spaces/ArubaEng/pages/1164385468/CEE+Aruba+CX+-+Log+Viewer

## 🚀 CLI and GUI Usage
Run LogViewer with no arguments to start the GUI:
```bash
LogViewer
```
---

## 🖥 GUI Navigation Guide

**Main GUI options:**

| Options          |              Description                       |
|------------------|------------------------------------------------|
| Upload .tar.gz   | Load a single bundle                           |
| Scan Directory   | Recursively find bundles                       |
| Analyze Selected | Parses and generates the HTML viewer           |
| Start Viewer     | Launches browser or carousel                   |
| Stop Viewer      | Stops running HTTP viewer                      |
| Clear            | Removes Pending/Error entries or deletes bundle|
| README           | Loads README.md into modal                     |
| Reopen GUI       | Previously parsed entries auto-loaded          |


**Other Notes:**
- Status bar shows real-time feedback
- Clear selected entries (Pending/Error or Analyzed)
- Previously parsed bundles are remembered using `~/.logviewer_state.json`

---

## 📦 Requirements

- Python 3.7+
- Pandas
- Streamlit
- **Tkinter** (must be available in system Python)
- `fastlogParser` (binary included, invoked via shell)
  - Linux: made executable automatically
  - Windows: used through **WSL** if available

