import os
import threading
import socket
import http.server
import socketserver

class ThreadedHTTPServer:
    def __init__(self, directory, port=None):
        self.directory = directory
        self.httpd = None
        self.thread = None
        self.port = port if port else self._find_free_port()

    def _find_free_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def start(self):
        os.chdir(self.directory)
        handler = http.server.SimpleHTTPRequestHandler
        self.httpd = socketserver.TCPServer(("", self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        print(f"✅ HTTP server started at http://localhost:{self.port}")

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.thread.join()
            print(f"🛑 HTTP server on port {self.port} stopped")

    def get_url(self):
        return f"http://localhost:{self.port}"

# Usage example (when integrated):
# server = ThreadedHTTPServer("log_analysis_results")
# server.start()
# print("Server running at:", server.get_url())
# ... later ...
# server.stop()
