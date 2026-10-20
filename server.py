import os
import sys
import json
import time
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import tracker_core as tc
import tracker

PORT = 8765
lock = threading.Lock()

def push_to_github_async(commit_msg="Auto-sync profiles & multi-platform stats [skip ci]"):
    def _worker():
        try:
            subprocess.run(["git", "add", "."], cwd=SCRIPT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=SCRIPT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "push", "origin", "main", "--force"], cwd=SCRIPT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[✓] Background GitHub sync completed.")
        except Exception as e:
            print(f"[-] GitHub sync note: {e}")
    threading.Thread(target=_worker, daemon=True).start()

class TrackerRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Cache-Control")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html", "/activity_dashboard.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            if os.path.exists(tc.INDEX_FILE):
                with open(tc.INDEX_FILE, "rb") as f:
                    self.wfile.write(f.read())
            return

        if path in ("/data.json", "/api/data"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            if os.path.exists(tc.DATA_JSON_FILE):
                with open(tc.DATA_JSON_FILE, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"{}")
            return

        self.send_response(404)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0]
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"

        if path == "/api/profiles":
            try:
                payload = json.loads(body)
                new_trainees = tc.normalize_trainees_list(payload.get("trainees", []))
                with lock:
                    cfg = tc.load_config()
                    cfg["trainees"] = new_trainees
                    cfg["last_cloud_sync_ts"] = int(time.time())
                    with open(tc.CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, indent=2, ensure_ascii=False)
                    tracker.run_once()
                push_to_github_async("Update trainee profiles from Browser UI")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._send_cors_headers()
                self.end_headers()
                with open(tc.DATA_JSON_FILE, "rb") as f:
                    self.wfile.write(f.read())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        if path == "/api/refresh":
            try:
                with lock:
                    tracker.run_once()
                push_to_github_async("Manual refresh from Browser UI [skip ci]")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._send_cors_headers()
                self.end_headers()
                with open(tc.DATA_JSON_FILE, "rb") as f:
                    self.wfile.write(f.read())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self._send_cors_headers()
        self.end_headers()

def periodic_background_worker():
    while True:
        time.sleep(300)  # Every 5 minutes
        try:
            with lock:
                tracker.run_once()
            push_to_github_async("Periodic 5m auto-update [skip ci]")
        except Exception as e:
            print(f"[-] Periodic worker error: {e}")

if __name__ == "__main__":
    print(f"[*] Starting initial multi-platform analysis...")
    with lock:
        tracker.run_once()
    t = threading.Thread(target=periodic_background_worker, daemon=True)
    t.start()
    print(f"[✓] Background Tracker Server listening on http://127.0.0.1:{PORT}")
    server = HTTPServer(("127.0.0.1", PORT), TrackerRequestHandler)
    server.serve_forever()

