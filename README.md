# LogViewer — Aruba Log Parser & Visualizer

**LogViewer** is a Python-based tool for parsing and visualizing logs collected from **Aruba CX switches**. It supports a variety of formats — including `.supportlog`, `event.log`, `critical.log`, and `journalctl` exports — even when embedded inside `.tar.gz` support bundles.

The result is an **interactive HTML dashboard** with filter, search, timeline, and tabbed views to streamline log analysis — and now includes a **CLI interface** for automation and repeatable workflows.

---

## 🔧 Features

- ✅ Parse `.tar.gz` support bundles directly
- ✅ Supports Aruba log formats: `event.log`, `critical.log`, `journal`, and `.supportlog`
- ✅ Extracts and organizes:
  - Regular logs
  - Fastlogs (via `fastlogParser`)
  - ISP output
  - `diagdump.txt` and `showtech.txt` into subfolders
- ✅ Generates offline **HTML viewer** with tabs:
  - Logs
  - Fastlogs
  - Diag Dumps
  - ShowTech
- ✅ Filtering by process, timestamp range, and keyword
- ✅ Persistent **state tracking** of parsed bundles
- ✅ CLI-Hybrid: Launch viewer from terminal
- ✅ Auto-assigns and reuses HTTP ports per bundle

---
## 🚀 Installation

git clone https://github.com/jasonhpe/LogViewer.git
cd LogViewer
pip install . --user
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc

🔁 Update

cd LogViewer
git pull
pip install . --user --force-reinstall

🧹 Uninstall
pip uninstall LogViewer

🕹️ CLI and GUI Usage

Run LogViewer with no arguments to start the GUI.

LogViewer

Run LogViewer --help to view available commands:

LogViewer --help

Analyze a support bundle

LogViewer analyze --path support1.tar.gz

LogViewer list

View a bundle in the browser

LogViewer view --bundle latest           # Launches the most recent
LogViewer view --bundle support1_log_analysis_results

ℹ️ Bundles are served on http://localhost:<auto-port> and cached for re-use.

🗂 Output Structure

support1.tar.gz_log_analysis_results/
├── parsed_logs.json
├── fastlog_index.json
├── diag_index.json
├── showtech_index.json
├── isp.txt
├── index.html
├── fastlogs/
├── feature/         ← diagdumps (grouped)
├── showtech/        ← sectioned showtech
└── log_viewer_TIMESTAMP.html

✅ Requirements
Python 3.7+

fastlogParser must be in your system PATH for .supportlog parsing


Made with 💻 by @jasonhpe

