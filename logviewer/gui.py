import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
from logviewer.parser import parse_bundle

class LogViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LogViewer GUI")
        self.root.geometry("900x500")

        self.port_base = 8000
        self.running_servers = {}
        self.analyzed_bundles = set()

        self.create_widgets()

    def create_widgets(self):
        title = tk.Label(self.root, text="LogViewer - Aruba Log Analysis GUI", font=("Helvetica", 18, "bold"), pady=10)
        title.pack()

        note = tk.Label(self.root, text="Upload or scan a directory for .tar.gz support bundles.", font=("Helvetica", 10), fg="gray")
        note.pack()

        frame = tk.Frame(self.root, pady=10)
        frame.pack()

        tk.Button(frame, text="Upload .tar.gz", command=self.select_file, bg="#007acc", fg="white").grid(row=0, column=0, padx=5)
        tk.Button(frame, text="Scan Directory", command=self.scan_directory, bg="#007acc", fg="white").grid(row=0, column=1, padx=5)

        self.tree = ttk.Treeview(self.root, columns=("path", "status"), show='headings', height=15)
        self.tree.heading("path", text="Support Bundle Path")
        self.tree.heading("status", text="Status")
        self.tree.column("path", width=600)
        self.tree.column("status", width=100)
        self.tree.pack(pady=10)

        action_frame = tk.Frame(self.root)
        action_frame.pack()

        tk.Button(action_frame, text="Analyze Selected", command=self.analyze_selected, bg="#28a745", fg="white").grid(row=0, column=0, padx=10)
        tk.Button(action_frame, text="Start HTTP Server", command=self.start_server, bg="#17a2b8", fg="white").grid(row=0, column=1, padx=10)
        tk.Button(action_frame, text="Stop HTTP Server", command=self.stop_server, bg="#dc3545", fg="white").grid(row=0, column=2, padx=10)

        self.status = tk.Label(self.root, text="Ready", anchor="w")
        self.status.pack(fill="x")

    def select_file(self):
        file = filedialog.askopenfilename(filetypes=[("Tar GZ Files", "*.tar.gz")])
        if file:
            self.add_bundle(file)

    def scan_directory(self):
        folder = filedialog.askdirectory()
        if folder:
            for path in Path(folder).rglob("*.tar.gz"):
                self.add_bundle(str(path))

    def add_bundle(self, filepath):
        if filepath not in self.analyzed_bundles:
            self.tree.insert("", "end", values=(filepath, "Pending"))

    def analyze_selected(self):
        for item in self.tree.selection():
            filepath = self.tree.item(item, "values")[0]
            self.tree.set(item, column="status", value="Analyzing")
            threading.Thread(target=self.run_analysis, args=(filepath, item), daemon=True).start()

    def run_analysis(self, filepath, tree_id):
        self.status.config(text=f"Analyzing {filepath}...")
        try:
            output_dir = f"log_analysis_results/{Path(filepath).stem}"
            os.makedirs(output_dir, exist_ok=True)
            parse_bundle(filepath, output_dir)
            self.analyzed_bundles.add(filepath)
            self.tree.set(tree_id, column="status", value="Analyzed")
            self.status.config(text=f"Done analyzing: {filepath}")
        except Exception as e:
            self.tree.set(tree_id, column="status", value="Error")
            self.status.config(text=f"Failed to analyze {filepath}: {e}")

    def start_server(self):
        for item in self.tree.selection():
            filepath = self.tree.item(item, "values")[0]
            output_dir = f"log_analysis_results/{Path(filepath).stem}"
            port = self.get_next_available_port()
            proc = subprocess.Popen(["python3", "-m", "http.server", str(port), "--directory", output_dir])
            self.running_servers[filepath] = (proc, port)
            self.status.config(text=f"Started server on port {port} for {filepath}")
            os.system(f"xdg-open http://localhost:{port} 2>/dev/null &")

    def stop_server(self):
        for item in self.tree.selection():
            filepath = self.tree.item(item, "values")[0]
            if filepath in self.running_servers:
                proc, port = self.running_servers.pop(filepath)
                proc.terminate()
                self.status.config(text=f"Stopped server on port {port} for {filepath}")

    def get_next_available_port(self):
        while any(p == self.port_base for _, p in self.running_servers.values()):
            self.port_base += 1
        return self.port_base

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
    root = tk.Tk()
    app = LogViewerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
