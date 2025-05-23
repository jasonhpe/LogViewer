# LogViewer — Aruba Log Parser & Visualizer

**LogViewer** is a Python-based GUI + CLI application to parse and visualize support bundles collected from **Aruba CX switches**. It handles `.tar.gz` support files, parses event/critical logs, `.supportlog` files (via `fastlogParser`), and generates a browsable **HTML dashboard** with filters, tabs, and a multi-bundle carousel view.

---

## 🚀 Features

- Parse `.tar.gz` Aruba support bundles
- Supports logs: `event.log`, `critical.log`, `journalctl`, `.supportlog`
- Fastlog processing via `fastlogParser`
- Extracts and organizes:
  - Logs
  - Fastlogs
  - ISP output
  - `diagdump.txt` and sectioned `showtech.txt`
- Offline HTML viewer with:
  - Logs
  - Fastlogs
  - Diag Dumps
  - ShowTech
- Powerful search + filtering:
  - By process name
  - Keyword
  - Timestamp range
  - Fastlog toggle
- GUI with persistent session state
- CLI mode for automation
- Reusable HTTP ports
- Viewer for multiple bundles
- Built-in README-based Help modal
- Progress bar during parsing
- Fully self-contained HTML output
- Logs, and timestamp range Normalized in UTC
- Added Error timeline chart

---

## 🔧 Installation

Go to https://github.hpe.com/settings/tokens

Create a fine-scoped PAT with expiration

Then use it via Git credential manager, GitHub CLI, or manual prompt on clone

```bash
xdg-settings set default-web-browser firefox.desktop
git config --global credential.helper store
git clone https://github.hpe.com/jason-sanchez/LogViewer.git
[Enter your github user-name]
[Enter the PAT] 
cd LogViewer
pip install . --user
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

---

### 🪟 Windows Users – WSL Required for Fastlog Parsing
To parse `.supportlog` files on Windows, you must have **WSL (Windows Subsystem for Linux)** installed.

#### 📥 Install WSL (once)
Run the following command in **PowerShell as Administrator**:
```powershell
wsl --install
```
Then restart your machine.

More: https://aka.ms/wslinstall

Once installed, LogViewer will automatically use WSL to invoke `fastlogParser` from Windows.

---

## 🔄 Update
```bash
cd LogViewer
git pull
pip install . --user --force-reinstall
```

## ❌ Uninstall
```bash
pip uninstall LogViewer
```

---

## 🚀 CLI and GUI Usage
Run LogViewer with no arguments to start the GUI:
```bash
LogViewer
```

![image](https://github.hpe.com/jason-sanchez/LogViewer/assets/76252/080d17ac-efd8-4142-bf10-55627648a3c8)

---

## 🖥 GUI Navigation Guide

**Main GUI options:**

| Button            | Description                                    |
|------------------|------------------------------------------------|
| Upload .tar.gz   | Load a single bundle                           |
| Scan Directory   | Recursively find bundles                       |
| Analyze Selected | Parses and generates the HTML viewer           |
| Start Viewer     | Launches browser or carousel                   |
| Stop Viewer      | Stops running HTTP viewer                      |
| Clear            | Removes Pending/Error entries or deletes bundle |
| Help (?)         | Loads README.md into modal                     |
| Reopen GUI       | Previously parsed entries auto-loaded          |

**Other Notes:**
- Status bar shows real-time feedback
- Clear selected entries (Pending/Error or Analyzed)
- Previously parsed bundles are remembered using `~/.logviewer_state.json`

---

## 🔧 CLI Examples

Run LogViewer with `--help`:
```bash
LogViewer --help
LogViewer analyze --help
LogViewer view --help
```

### Analyze a support bundle
```bash
LogViewer analyze --path support1.tar.gz
```

### Analyze and open viewer
```bash
LogViewer analyze --path support1.tar.gz --open
```

### List parsed bundles
```bash
LogViewer list
```

### View a parsed bundle
```bash
LogViewer view --bundle latest
LogViewer view --bundle support1_log_analysis_results
```

---

## 🧭 How to Use Carousel Viewer

Launch GUI:
```bash
LogViewer
```
- Upload or scan for multiple `.tar.gz` bundles
- Select 2 or more parsed entries
- Click **Start Viewer** to open carousel tab in browser

Only bundles with valid `parsed_logs.json` will appear. `index.html` is no longer generated — viewer is now powered by Streamlit.

![image](https://github.hpe.com/jason-sanchez/LogViewer/assets/76252/db997703-0801-4526-a4c8-d7443c198f68)

---

## 📁 Output Structure

```bash
support1.tar.gz_log_analysis_results/
├── parsed_logs.json
├── fastlog_index.json
├── diag_index.json
├── showtech_index.json
├── isp.txt
├── README.md
├── fastlogs/
├── feature/         # diagdumps
├── showtech/        # sectioned output
```

---

## 📦 Requirements

- Python 3.7+
- Pandas
- Streamlit
- **Tkinter** (must be available in system Python)
- `fastlogParser` (binary included, invoked via shell)
  - Linux: made executable automatically
  - Windows: used through **WSL** if available

