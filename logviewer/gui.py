try:
    import tkinter
except ImportError:
    print("\u274c Tkinter is not installed. Please install it manually for GUI support. Use 'sudo apt install python3-tk'")
    exit(1)

import psutil
import multiprocessing
import os
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from pathlib import Path
import shutil
import json
from logviewer.parser import find_readme, parse_bundle
from logviewer.state import (
    load_state, save_state,
    add_parsed_bundle, get_parsed_bundles,
    get_next_available_port
)

class LogViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LogViewer GUI")
        self.root.geometry("900x550")

        self.state = load_state()
        self.running_servers = {}
        self.viewing_in_progress = False

        self.create_widgets()
        self.load_previous_bundles()

    
    def update_cpu_usage(self):
    usage = psutil.cpu_percent(interval=1)
    self.cpu_usage_label.config(text=f"CPU Usage: {usage}%")
    self.root.after(1000, self.update_cpu_usage)
    
    
    def create_widgets(self):
        
        
        
        tk.Label(self.root, text="Upload or scan a directory for .tar.gz support bundles.", font=("Helvetica", 10), fg="gray").pack()

        frame = tk.Frame(self.root, pady=10)
        frame.pack()
        tk.Button(frame, text="Upload .tar.gz", command=self.select_file, bg="#007acc", fg="white").grid(row=0, column=0, padx=5)
        tk.Button(frame, text="Scan Directory", command=self.scan_directory, bg="#007acc", fg="white").grid(row=0, column=1, padx=5)
        tk.Button(frame, text="Clear", command=self.clear_entries, bg="#ffc107", fg="black").grid(row=0, column=2, padx=5)

        
        self.worker_var = tk.IntVar(value=max(1, multiprocessing.cpu_count() - 1))
        worker_frame = tk.Frame(self.root)
        worker_frame.pack(pady=(0, 5))
        tk.Label(worker_frame, text="Max Parallel Parses:").pack(side="left", padx=5)
        tk.Spinbox(worker_frame, from_=1, to=multiprocessing.cpu_count(), textvariable=self.worker_var, width=5, state="readonly").pack(side="left")
        tk.Label(self.root, text="LogViewer - Aruba Log Analysis GUI", font=("Helvetica", 18, "bold"), pady=10).pack()
        self.cpu_usage_label = tk.Label(self.root, text="CPU Usage: 0%", fg="gray")
        self.cpu_usage_label.pack()
        self.update_cpu_usage()
        
        self.scan_status = tk.Label(self.root, text="Files scanned: 0", anchor="w")
        self.scan_status.pack()

        self.tree_frame = tk.Frame(self.root)
        self.tree_frame.pack(fill="both", expand=True)

        self.tree_scroll_y = tk.Scrollbar(self.tree_frame)
        self.tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_scroll_x = tk.Scrollbar(self.tree_frame, orient='horizontal')
        self.tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree = ttk.Treeview(self.tree_frame, columns=("path", "status"), show='headings', height=15,
                                 yscrollcommand=self.tree_scroll_y.set,
                                 xscrollcommand=self.tree_scroll_x.set)
        self.tree.heading("path", text="Support Bundle Path")
        self.tree.heading("status", text="Status")
        self.tree.column("path", width=700, anchor="w")
        self.tree.column("status", width=100, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree_scroll_y.config(command=self.tree.yview)
        self.tree_scroll_x.config(command=self.tree.xview)

        action_frame = tk.Frame(self.root)
        action_frame.pack(pady=5)
        tk.Button(action_frame, text="Analyze Selected", command=self.analyze_selected, bg="#28a745", fg="white").grid(row=0, column=0, padx=10)
        tk.Button(action_frame, text="Start Viewer", command=self.start_viewer, bg="#17a2b8", fg="white").grid(row=0, column=1, padx=10)
        tk.Button(action_frame, text="Stop Viewer", command=self.stop_viewer, bg="#dc3545", fg="white").grid(row=0, column=2, padx=10)

        self.status = tk.Label(self.root, text="Ready", anchor="w")
        self.status.pack(fill="x")

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", padx=10)
        self.progress.stop()
        self.progress.pack_forget()

    def select_file(self):
        file = filedialog.askopenfilename(filetypes=[("Tar GZ Files", "*.tar.gz")])
        if file:
            self.add_bundle(file)

    def scan_directory(self):
        folder = filedialog.askdirectory()
        count = 0
        if folder:
            for path in Path(folder).rglob("*.tar.gz"):
                self.add_bundle(str(path))
                count += 1
            self.scan_status.config(text=f"Files scanned: {count}")

    def clear_entries(self):
        selected = self.tree.selection()
        to_remove = []

        if not selected:
            confirm = messagebox.askyesno("Clear Pending/Error", "Clear all unprocessed (Pending/Error) entries?")
            if not confirm:
                return
            for item in self.tree.get_children():
                status = self.tree.item(item, "values")[1]
                if status in ("Pending", "Error"):
                    to_remove.append(item)
        else:
            for item in selected:
                path, status = self.tree.item(item, "values")
                if status in ("Pending", "Error"):
                    to_remove.append(item)
                elif status == "Analyzed":
                    confirm = messagebox.askyesno("Delete Parsed?", f"Delete parsed result and remove '{path}'?")
                    if confirm:
                        parsed = get_parsed_bundles(self.state).get(path)
                        if parsed:
                            shutil.rmtree(parsed["output_path"], ignore_errors=True)
                        self.state["parsed_bundles"].pop(path, None)
                        to_remove.append(item)

        for item in to_remove:
            self.tree.delete(item)

        save_state(self.state)
        self.status.config(text="Updated entries after clear operation.", fg="orange")
    

    def add_bundle(self, filepath):
        for row in self.tree.get_children():
            if self.tree.item(row, "values")[0] == filepath:
                return
        analyzed = filepath in get_parsed_bundles(self.state)
        self.tree.insert("", "end", values=(filepath, "Analyzed" if analyzed else "Pending"))

    def load_previous_bundles(self):
        # Load from existing saved state
        parsed = get_parsed_bundles(self.state)

        # Track which paths are already listed in state
        known_paths = set(parsed.keys())

        # Add those that still exist
        for bundle_path, meta in parsed.items():
            if os.path.exists(bundle_path):
                self.tree.insert("", "end", values=(bundle_path, "Analyzed"))

        # Fallback: scan current folder for _log_analysis_results dirs
        for child in Path(".").iterdir():
            if child.is_dir() and child.name.endswith("_log_analysis_results"):
                parsed_log = child / "parsed_logs.json"
                if parsed_log.exists():
                    # Check if already tracked in state
                    if str(child) not in known_paths:
                        self.tree.insert("", "end", values=(str(child), "Analyzed"))
                        self.state["parsed_bundles"][str(child)] = {
                            "output_path": str(child.resolve())
                        }

        # Save updated state if we added anything
        save_state(self.state)

    def analyze_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("No Selection", "Please select at least one support bundle to analyze.")
            return

        filepaths = [self.tree.item(item, "values")[0] for item in selected_items]

        # Update status to Analyzing in GUI
        for item in selected_items:
            self.tree.set(item, column="status", value="Analyzing")

        self.status.config(text="Analyzing selected bundles...", fg="blue")
        self.show_progress()

        def background_parse():
            from logviewer.parser import parse_multiple_bundles
            results = parse_multiple_bundles(filepaths, workers=self.worker_var.get())

            for result in results:
                for item in self.tree.get_children():
                    path = self.tree.item(item, "values")[0]
                    if path == result["path"]:
                        if result["status"] == "Success":
                            add_parsed_bundle(self.state, result["path"], result["output"])
                            self.tree.set(item, column="status", value="Analyzed")
                        else:
                            self.tree.set(item, column="status", value="Error")
                            print(f"❌ Failed to parse {result['path']}: {result.get('error')}")

            save_state(self.state)
            self.status.config(text="Done analyzing selected bundles.", fg="green")
            self.hide_progress()

        threading.Thread(target=background_parse, daemon=True).start()

    def run_analysis(self, filepath, tree_id):
        self.status.config(text=f"Analyzing {filepath}...")
        self.show_progress()
        try:
            output_dir = f"{Path(filepath).stem}_log_analysis_results"
            if not os.path.exists(os.path.join(output_dir, "parsed_logs.json")):
                parse_bundle(filepath, output_dir)
            add_parsed_bundle(self.state, filepath, output_dir)
            self.tree.set(tree_id, column="status", value="Analyzed")
            self.status.config(text=f"Done analyzing: {filepath}")
        except Exception as e:
            self.tree.set(tree_id, column="status", value="Error")
            self.status.config(text=f"Failed to analyze {filepath}: {e}", fg="red")
        finally:
            self.hide_progress()



    def start_viewer(self):
        selected = self.tree.selection()
        if self.viewing_in_progress:
            self.status.config(text="Viewer already running", fg="orange")
            return

        parsed_bundles = get_parsed_bundles(self.state)
        entries = []

        for item in selected:
            filepath = self.tree.item(item, "values")[0]
            meta = parsed_bundles.get(filepath)
            if meta and os.path.exists(os.path.join(meta["output_path"], "parsed_logs.json")):
                entries.append({
                    "name": os.path.basename(filepath),
                    "path": os.path.abspath(meta["output_path"])
                })

        if not entries:
            # Fallback: try scanning log_analysis_results/
            fallback_dir = Path(".")
            recovered = []
            for child in fallback_dir.iterdir():
                if child.is_dir() and child.name.endswith("_log_analysis_results"):
                    parsed_path = child / "parsed_logs.json"
                    if parsed_path.exists():
                        recovered.append({
                            "name": child.name,
                            "path": str(child.resolve())
                        })
                        # Optionally repopulate state
                        self.state["parsed_bundles"][str(child)] = {
                            "output_path": str(child.resolve())
                        }

            if recovered:
                save_state(self.state)
                entries = recovered
                self.status.config(text=f"Recovered {len(entries)} parsed bundles", fg="blue")
            else:
                self.status.config(text="No valid parsed bundles to view", fg="red")
                return

        config = {
            "mode": "carousel" if len(entries) > 1 else "single",
            "bundle_list": entries if len(entries) > 1 else None,
            "bundle_path": entries[0]["path"] if len(entries) == 1 else None
        }

        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)

        port = get_next_available_port(self.state)
        proc = subprocess.Popen(["streamlit", "run", "app.py", "--server.port", str(port)])
        self.running_servers["streamlit"] = (proc, port)
        self.status.config(text=f"Viewer running on http://localhost:{port}", fg="green")
        self.viewing_in_progress = True

        # Platform-safe open browser
        if os.name == "nt":  # Windows
            os.system(f"start http://localhost:{port}")
        elif os.name == "posix":
            os.system(f"xdg-open http://localhost:{port} 2>/dev/null &")

    def stop_viewer(self):
        if not self.running_servers:
            self.status.config(text="No viewer is currently running", fg="orange")
            return

        for key, (proc, port) in self.running_servers.items():
            proc.terminate()
            self.status.config(text=f"Stopped viewer on port {port}", fg="gray")

        self.running_servers.clear()
        self.viewing_in_progress = False

    def show_progress(self):
        self.progress.pack(fill="x", padx=10)
        self.progress.start(10)

    def hide_progress(self):
        self.progress.stop()
        self.progress.pack_forget()

    def on_close(self):
        for proc, _ in self.running_servers.values():
            proc.terminate()
        save_state(self.state)
        self.root.destroy()


def launch_gui():
    root = tk.Tk()
    app = LogViewerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
