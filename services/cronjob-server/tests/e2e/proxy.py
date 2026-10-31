"""Test-only HTTP fault injector; never packaged in either service image."""

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

condition = threading.Condition()
state = {"hold_mutations": False, "hold_snapshots": False, "corrupt_snapshot": False,
         "mutation_committed": False, "snapshot_captured": False}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body):
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def handle_request(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path == "/__test/state":
            with condition:
                if self.command == "POST":
                    state.update(json.loads(body))
                    condition.notify_all()
                self.reply(200, json.dumps(state).encode())
            return
        headers = {k: v for k, v in self.headers.items() if k.lower() in {
            "content-type", "idempotency-key", "x-demo-user-id"}}
        request = urllib.request.Request("http://source:8000" + self.path,
            data=body or None, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                status, result = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, result = exc.code, exc.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            self.reply(503, b'{"error":{"code":"SOURCE_UNAVAILABLE"}}')
            return
        with condition:
            if self.path == "/v1/snapshot" and status == 200:
                state["snapshot_captured"] = True
                while state["hold_snapshots"]:
                    condition.wait(timeout=1)
                if state["corrupt_snapshot"]:
                    snapshot = json.loads(result)
                    snapshot["complete"] = False
                    result = json.dumps(snapshot).encode()
            elif self.command in {"POST", "PATCH", "DELETE"} and 200 <= status < 300:
                state["mutation_committed"] = True
                while state["hold_mutations"]:
                    condition.wait(timeout=1)
        self.reply(status, result)

    do_GET = do_POST = do_PATCH = do_DELETE = handle_request


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
