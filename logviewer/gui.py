try:
    import tkinter
except ImportError:
    print("\u274c Tkinter is not installed. Please install it manually for GUI support. Use 'sudo apt install python3-tk'")
    exit(1)

from datetime import datetime    
import queue
import psutil
import time
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
    add_parsed_bundle, remove_parsed_bundle,
    get_parsed_bundles, get_next_available_port
)

class LogViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LogViewer GUI v1.1.1-beta.3")
        self.root.geometry("900x550")

        # Scrollable Canvas Setup
        self.canvas = tk.Canvas(self.root)
        self.scroll_y = tk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)

        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll_y.pack(side="right", fill="y")

        # .scrollable_frame inside create_widgets
        self.running_servers = {}
        self.viewing_in_progress = False

        self.create_widgets()  
        self.debug_queue = queue.Queue()
        self.root.after(500, self.update_debug_log)
        self.load_previous_bundles()

        from logviewer import parser
        parser.set_logger(self.log_debug)

    def log_debug(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.debug_queue.put(f"[{timestamp}] {message}")

    def update_debug_log(self):
        while not self.debug_queue.empty():
            msg = self.debug_queue.get_nowait()
            self.debug_output.config(state="normal")
            self.debug_output.insert("end", f"{msg}\n")
            self.debug_output.see("end")
        self.debug_output.config(state="disabled")
        self.root.after(500, self.update_debug_log)
        
    
    def update_cpu_usage(self):
        usage = psutil.cpu_percent(interval=1)
        self.cpu_usage_label.config(text=f"CPU Usage: {usage}%")
        self.root.after(1000, self.update_cpu_usage)
    
    
    def create_widgets(self):
        
        
        
        tk.Label(self.scrollable_frame, text="Upload or scan a directory for .tar.gz support bundles.", font=("Helvetica", 10), fg="gray").pack()

        frame = tk.Frame(self.scrollable_frame, pady=10)
        frame.pack()
        tk.Button(frame, text="Upload .tar.gz", command=self.select_file, bg="#007acc", fg="white").grid(row=0, column=0, padx=5)
        tk.Button(frame, text="Scan Directory", command=self.scan_directory, bg="#007acc", fg="white").grid(row=0, column=1, padx=5)
        tk.Button(frame, text="Clear", command=self.clear_entries, bg="#ffc107", fg="black").grid(row=0, column=2, padx=5)
        tk.Button(frame, text="View README", command=self.show_readme, bg="#6c757d", fg="white").grid(row=0, column=3, padx=5)


        self.debug_output = tk.Text(self.scrollable_frame, height=10, state="disabled", bg="#f8f8f8", fg="black", wrap="word")
        self.debug_output.pack(fill="both", expand=False, padx=10, pady=(5, 10))

        
        self.worker_var = tk.IntVar(value=max(1, multiprocessing.cpu_count() - 1))
        worker_frame = tk.Frame(self.scrollable_frame)
        worker_frame.pack(pady=(0, 5))
        tk.Label(worker_frame, text="Max Parallel Parses:").pack(side="left", padx=5)
        tk.Spinbox(worker_frame, from_=1, to=multiprocessing.cpu_count(), textvariable=self.worker_var, width=5, state="readonly").pack(side="left")
        tk.Label(self.scrollable_frame, text="LogViewer - Aruba Log Analysis GUI", font=("Helvetica", 18, "bold"), pady=10).pack()
        self.cpu_usage_label = tk.Label(self.scrollable_frame, text="CPU Usage: 0%", fg="gray")
        self.cpu_usage_label.pack()
        self.update_cpu_usage()
        
        self.scan_status = tk.Label(self.scrollable_frame, text="Files scanned: 0", anchor="w")
        self.scan_status.pack()

        self.tree_frame = tk.Frame(self.scrollable_frame)
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

        action_frame = tk.Frame(self.scrollable_frame)
        action_frame.pack(pady=5)
        self.include_fastlogs = tk.BooleanVar(value=True)
        self.include_vsf = tk.BooleanVar(value=True)
        self.include_prevboot = tk.BooleanVar(value=True)
        self.include_linecards = tk.BooleanVar(value=True)

        tk.Checkbutton(self.scrollable_frame, text="Parse Fastlogs", variable=self.include_fastlogs).pack()
        tk.Checkbutton(self.scrollable_frame, text="Parse VSF Members", variable=self.include_vsf).pack()
        tk.Checkbutton(self.scrollable_frame, text="Parse Linecard logs", variable=self.include_linecards).pack()
        tk.Checkbutton(self.scrollable_frame, text="Parse Previous Boot Logs", variable=self.include_prevboot).pack()
        
        tk.Button(action_frame, text="Analyze Selected", command=self.analyze_selected, bg="#28a745", fg="white").grid(row=0, column=0, padx=10)
        tk.Button(action_frame, text="Start Viewer", command=self.start_viewer, bg="#17a2b8", fg="white").grid(row=0, column=1, padx=10)
        tk.Button(action_frame, text="Stop Viewer", command=self.stop_viewer, bg="#dc3545", fg="white").grid(row=0, column=2, padx=10)

        self.status = tk.Label(self.scrollable_frame, text="Ready", anchor="w")
        self.status.pack(fill="x")

        self.progress = ttk.Progressbar(self.scrollable_frame, mode="indeterminate")
        self.progress.pack(fill="x", padx=10)
        self.progress.stop()
        self.progress.pack_forget()

    def show_readme(self):
        readme_path = Path("README.md")
        if not readme_path.exists():
            messagebox.showerror("README Not Found", "README.md file not found in the current directory.")
            return

        top = tk.Toplevel(self.scrollable_frame)
        top.title("README.md")
        top.geometry("700x500")

        text_widget = tk.Text(top, wrap="word", bg="#f8f8f8")
        text_widget.pack(fill="both", expand=True)

        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
            text_widget.insert("1.0", content)

        text_widget.config(state="disabled")

    def select_file(self):
        file = filedialog.askopenfilename(filetypes=[("Tar GZ Files", "*.tar.gz")])
        if file:
            self.add_bundle(file)

    def scan_directory(self):
        def background_scan():
            folder = filedialog.askdirectory()
            count = 0
            if folder:
                for path in Path(folder).rglob("*.tar.gz"):
                    self.add_bundle(str(path))
                    count += 1
                self.scan_status.config(text=f"Files scanned: {count}")
                self.log_debug(f"📦 Found {count} .tar.gz files.")
        
        threading.Thread(target=background_scan, daemon=True).start()
        

    def clear_entries(self):
        selected = self.tree.selection()
        to_remove = []

        if not selected:
            confirm = messagebox.askyesno("Clear Pending/Error", "Clear all unprocessed (Pending/Error) entries?")
            if not confirm:
                self.log_debug("❌ Clear canceled by user.")
                return
            self.log_debug("🧹 Clearing all unprocessed (Pending/Error) entries...")
            for item in self.tree.get_children():
                path, status = self.tree.item(item, "values")
                if status in ("Pending", "Error"):
                    to_remove.append(item)
                    self.log_debug(f"🗑️ Removing: {path} [{status}]")
        else:
            self.log_debug(f"🧹 Clearing selected {len(selected)} item(s)...")
            for item in selected:
                path, status = self.tree.item(item, "values")
                if status in ("Pending", "Error"):
                    to_remove.append(item)
                    self.log_debug(f"🗑️ Removing: {path} [{status}]")
                elif status == "Analyzed":
                    confirm = messagebox.askyesno("Delete Parsed?", f"Delete parsed result and remove '{path}'?")
                    if confirm:
                        parsed = get_parsed_bundles().get(path)
                        if parsed:
                            output_path = parsed["output_path"]
                            if os.path.exists(output_path):
                                shutil.rmtree(output_path, ignore_errors=True)
                                self.log_debug(f"🧨 Deleted parsed output: {output_path}")
                        remove_parsed_bundle(path)
                        self.log_debug(f"🗑️ Removed parsed entry: {path}")
                        to_remove.append(item)
                    else:
                        self.log_debug(f"🚫 Skipped deletion of: {path}")

        for item in to_remove:
            self.tree.delete(item)

        self.status.config(text="Updated entries after clear operation.", fg="orange")
        self.log_debug("✅ Clear operation completed.")
        
    

    def add_bundle(self, filepath):
        for row in self.tree.get_children():
            if self.tree.item(row, "values")[0] == filepath:
                self.log_debug(f"⚠️ Skipped duplicate bundle: {filepath}")
                return
        analyzed = filepath in get_parsed_bundles()
        status = "Analyzed" if analyzed else "Pending"
        self.tree.insert("", "end", values=(filepath, status))
        self.log_debug(f"📥 Added bundle: {filepath} [{status}]")

    def load_previous_bundles(self):
        parsed = get_parsed_bundles()
        known_paths = set(parsed.keys())

        existing_tree_paths = {
            self.tree.item(item, "values")[0]
            for item in self.tree.get_children()
        }

        for bundle_path, meta in parsed.items():
            if os.path.exists(bundle_path) and bundle_path not in existing_tree_paths:
                self.tree.insert("", "end", values=(bundle_path, "Analyzed"))

        for child in Path(".").iterdir():
            if child.is_dir() and child.name.endswith("_log_analysis_results"):
                parsed_log = child / "parsed_logs.json"
                if parsed_log.exists():
                    bundle_path = str(child)
                    if bundle_path not in known_paths and bundle_path not in existing_tree_paths:
                        self.tree.insert("", "end", values=(bundle_path, "Analyzed"))
                        add_parsed_bundle(bundle_path, str(child.resolve()))
                        

       

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
            self.log_debug(f"🛠️ Starting analysis with {self.worker_var.get()} workers.")
            from logviewer.parser import parse_multiple_bundles, set_logger
            set_logger(self.log_debug)
            
            results = parse_multiple_bundles(
                filepaths,
                workers=self.worker_var.get(),
                options={
                    "include_fastlogs": self.include_fastlogs.get(),
                    "include_vsf": self.include_vsf.get(),
                    "include_linecards": self.include_linecards.get(),
                    "include_prevboot": self.include_prevboot.get()
                }
            )

            self.log_debug(f"✅ Parsing completed for {len(results)} bundles.")

            for result in results:
                for item in self.tree.get_children():
                    path = self.tree.item(item, "values")[0]
                    if path == result["path"]:
                        if result["status"] == "Success":
                            
                            add_parsed_bundle(result["path"], result["output"])
                            self.tree.set(item, column="status", value="Analyzed")
                            self.log_debug(f"✅ Parsed {result['path']} → {result['output']}")
                        else:
                            self.tree.set(item, column="status", value="Error")
                            self.log_debug(f"❌ Failed to parse {result['path']}: {result.get('error')}")

            
            self.status.config(text="Done analyzing selected bundles.", fg="green")
            self.hide_progress()

        threading.Thread(target=background_parse, daemon=True).start()

    def run_analysis(self, filepath, tree_id):
        self.status.config(text=f"Analyzing {filepath}...")
        self.show_progress()
        try:
            output_dir = f"{Path(filepath).stem}_log_analysis_results"
            if not os.path.exists(os.path.join(output_dir, "parsed_logs.json")):
                from logviewer import parser
                parser.set_logger(self.log_debug)
                parse_bundle(filepath, output_dir)
            add_parsed_bundle(filepath, output_dir)
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
            self.log_debug("⚠️ Viewer already running. Skipping launch.")
            return

        parsed_bundles = get_parsed_bundles()
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
                        add_parsed_bundle(str(child), str(child.resolve()))
            if recovered:
                entries = recovered
                self.status.config(text=f"Recovered {len(entries)} parsed bundles", fg="blue")
                self.log_debug(f"🔄 Recovered {len(entries)} parsed bundles from fallback scan.")
            else:
                self.status.config(text="No valid parsed bundles to view", fg="red")
                self.log_debug("❌ No parsed bundles available to start the viewer.")
                return

        config = {
            "mode": "carousel" if len(entries) > 1 else "single",
            "bundle_list": entries if len(entries) > 1 else None,
            "bundle_path": entries[0]["path"] if len(entries) == 1 else None
        }

        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        self.log_debug(f"⚙️ Created config.json with {len(entries)} bundle(s)")

        port = get_next_available_port()
        self.log_debug(f"🚀 Launching Streamlit on port {port}...")

        proc = subprocess.Popen(
            ["streamlit", "run", "app.py", "--server.port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )

        time.sleep(2)

        if proc.poll() is not None:
            out, err = proc.communicate()
            self.status.config(text="❌ Viewer failed to launch", fg="red")
            self.log_debug("❌ Streamlit failed to launch. Output below:")
            self.log_debug(out.decode(errors="ignore"))
            self.log_debug(err.decode(errors="ignore"))
            return

        self.running_servers["streamlit"] = (proc, port)
        self.status.config(text=f"Viewer running on http://localhost:{port}", fg="green")
        self.log_debug(f"✅ Viewer running at http://localhost:{port}")
        self.viewing_in_progress = True

        if os.name == "nt":
            os.system(f"start http://localhost:{port}")
        elif os.name == "posix":
            os.system(f"xdg-open http://localhost:{port} 2>/dev/null &")

    def stop_viewer(self):
        if not self.running_servers:
            self.status.config(text="No viewer is currently running", fg="orange")
            self.log_debug(f"No viewer is currently running")
            
            return

        for key, (proc, port) in self.running_servers.items():
            proc.terminate()
            self.status.config(text=f"Stopped viewer on port {port}", fg="gray")
            self.log_debug(f"🛑 Terminating viewer on port {port}")

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
       
        self.root.destroy()


def launch_gui():
    root = tk.Tk()
    app = LogViewerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
