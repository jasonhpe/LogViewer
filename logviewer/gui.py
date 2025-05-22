try:
    import tkinter
except ImportError:
    print("❌ Tkinter is not installed. Please install it manually for GUI support. Use 'sudo apt install python3-tk'")
    exit(1)
    
import os
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from pathlib import Path
import shutil
import json
from logviewer.parser import find_readme
from logviewer.parser import parse_bundle
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
        self.port_base = 8001
        self.running_servers = {}
        self.viewing_in_progress = False

        self.create_widgets()
        self.load_previous_bundles()

    def create_widgets(self):
        title = tk.Label(self.root, text="LogViewer - Aruba Log Analysis GUI", font=("Helvetica", 18, "bold"), pady=10)
        title.pack()

        note = tk.Label(self.root, text="Upload or scan a directory for .tar.gz support bundles.", font=("Helvetica", 10), fg="gray")
        note.pack()

        frame = tk.Frame(self.root, pady=10)
        frame.pack()

        tk.Button(frame, text="Upload .tar.gz", command=self.select_file, bg="#007acc", fg="white").grid(row=0, column=0, padx=5)
        tk.Button(frame, text="Scan Directory", command=self.scan_directory, bg="#007acc", fg="white").grid(row=0, column=1, padx=5)
        tk.Button(frame, text="Clear", command=self.clear_entries, bg="#ffc107", fg="black").grid(row=0, column=2, padx=5)

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
        tk.Button(action_frame, text="Start Viewer", command=self.start_server, bg="#17a2b8", fg="white").grid(row=0, column=1, padx=10)
        tk.Button(action_frame, text="Stop Viewer", command=self.stop_server, bg="#dc3545", fg="white").grid(row=0, column=2, padx=10)

        self.status = tk.Label(self.root, text="Ready", anchor="w")
        self.status.pack(fill="x")

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", padx=10)
        self.progress.stop()
        self.progress.pack_forget()
    
    def show_progress(self):
        self.progress.pack(fill="x", padx=10)
        self.progress.start(10)

    def hide_progress(self):
        self.progress.stop()
        self.progress.pack_forget()
        
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

    def load_previous_bundles(self):
        parsed = get_parsed_bundles(self.state)
        for bundle_path, meta in parsed.items():
            if os.path.exists(bundle_path):
                self.tree.insert("", "end", values=(bundle_path, "Analyzed"))

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

    def add_bundle(self, filepath):
        for row in self.tree.get_children():
            if self.tree.item(row, "values")[0] == filepath:
                return
        analyzed = filepath in get_parsed_bundles(self.state)
        self.tree.insert("", "end", values=(filepath, "Analyzed" if analyzed else "Pending"))

    def analyze_selected(self):
        for item in self.tree.selection():
            filepath = self.tree.item(item, "values")[0]
            self.tree.set(item, column="status", value="Analyzing")
            threading.Thread(target=self.run_analysis, args=(filepath, item), daemon=True).start()

    def run_analysis(self, filepath, tree_id):
        self.status.config(text=f"Analyzing {filepath}...")
        self.show_progress()
        try:
            output_dir = f"{Path(filepath).stem}_log_analysis_results"
            if not os.path.exists(os.path.join(output_dir, "index.html")):
                parse_bundle(filepath, output_dir)
            add_parsed_bundle(self.state, filepath, output_dir)
            self.tree.set(tree_id, column="status", value="Analyzed")
            self.status.config(text=f"Done analyzing: {filepath}")
        except Exception as e:
            self.tree.set(tree_id, column="status", value="Error")
            self.status.config(text=f"Failed to analyze {filepath}: {e}", fg="red")
        finally:
            self.hide_progress() 
        
    def start_server(self):
        selected = self.tree.selection()
        if self.viewing_in_progress:
            self.status.config(text="Viewer is already in progress.", fg="orange")
            return

        if len(selected) > 1:
            self.view_carousel(selected)
            return

        for item in selected:
            filepath = self.tree.item(item, "values")[0]
            parsed = get_parsed_bundles(self.state).get(filepath)
            if not parsed:
                self.status.config(text="No parsed data available")
                continue
            output_dir = parsed["output_path"]
            port = parsed.get("port") or get_next_available_port(self.state)
            proc = subprocess.Popen(["python3", "-m", "http.server", str(port), "--directory", output_dir])
            self.running_servers[filepath] = (proc, port)
            self.tree.set(item, column="status", value=f"Viewing on port {port}")
            parsed["port"] = port
            add_parsed_bundle(self.state, filepath, output_dir, port)
            self.status.config(text=f"Started server on port {port} for {filepath}")
            os.system(f"xdg-open http://localhost:{port} 2>/dev/null &")
            self.viewing_in_progress = True

    def view_carousel(self, selected):
        entries = []
        paths = []

        for item in selected:
            filepath = self.tree.item(item, "values")[0]
            meta = get_parsed_bundles(self.state).get(filepath)
            if meta and os.path.exists(os.path.join(meta["output_path"], "index.html")):
                bundle_path = os.path.abspath(meta["output_path"])
                entries.append({
                    "name": os.path.basename(filepath),
                    "url": f"{os.path.basename(bundle_path)}/index.html"
                })
                paths.append(bundle_path)

        if not entries:
            self.status.config(text="No valid bundles to show.")
            return

        parent_dir = os.path.commonpath(paths)
        bundle_json = os.path.join(parent_dir, "bundle_list.json")
        with open(bundle_json, "w") as f:
            json.dump(entries, f, indent=2)

        carousel_html = os.path.join(parent_dir, "carousel_viewer.html")
        template_path = os.path.join(os.path.dirname(__file__), "templates", "carousel_viewer.html")
        shutil.copy(template_path, carousel_html)

        # Copy README.md to the parent dir so carousel can access it
        readme_src = find_readme()
        if readme_src:
            try:
                shutil.copy(readme_src, os.path.join(parent_dir, "README.md"))
                print(f"📄 Copied README.md → {parent_dir}")
            except Exception as e:
                print(f"❌ Failed to copy README.md for carousel: {e}")
        else:
            print("⚠️ README.md not found for carousel view.")

        port = get_next_available_port(self.state)
        proc = subprocess.Popen(["python3", "-m", "http.server", str(port), "--directory", parent_dir])
        self.running_servers["__carousel__"] = (proc, port)
        for item in selected:
            filepath = self.tree.item(item, "values")[0]
            self.tree.set(item, column="status", value=f"Viewing on port {port} (carousel)")
        os.system(f"xdg-open http://localhost:{port}/carousel_viewer.html 2>/dev/null &")
        self.status.config(text=f"Opened carousel viewer on port {port}", fg="green")
        self.viewing_in_progress = True

    def stop_server(self):
        if not self.running_servers:
            self.status.config(text="No viewer is currently running.", fg="orange")
            return

        for key, (proc, port) in list(self.running_servers.items()):
            proc.terminate()
            self.status.config(text=f"Stopped server on port {port} for {key}", fg="gray")

            # Reset state entry (remove port)
            if key in self.state["parsed_bundles"]:
                self.state["parsed_bundles"][key].pop("port", None)

            for item in self.tree.get_children():
                path, status = self.tree.item(item, "values")
                if path == key or "Viewing on port" in status:
                    self.tree.set(item, column="status", value="Analyzed")

        self.running_servers.clear()
        self.viewing_in_progress = False
        save_state(self.state)

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
