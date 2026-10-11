#!/usr/bin/env python3
"""A stand-in WLED unit for the setup check: just enough of the JSON API that
gardenroom.py uses (/json, /json/cfg, POST /json/state), plus a sink for the
optional Home Assistant webhook. It keeps what it was sent so the check can
assert on it.

    python3 scripts/fake_wled.py 18081      # then GET /_last to see the last POST
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

STATE = {"on": False, "bri": 128, "udpn": {"send": False, "recv": True},
         "seg": [{"id": 0, "fx": 0, "col": [[255, 160, 80], [0, 0, 0], [0, 0, 0]]}]}
INFO = {"name": "fake-wled", "ver": "0.15.0",
        "leds": {"count": 300, "pwr": 120, "maxpwr": 850, "lc": 1}}
CFG = {"hw": {"led": {"total": 300, "maxpwr": 850, "ledma": 55,
                      "ins": [{"len": 300, "maxpwr": 850, "ledma": 55}]}}}
LAST = {}


class H(BaseHTTPRequestHandler):
    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/json":
            return self._send({"state": STATE, "info": INFO})
        if self.path == "/json/cfg":
            return self._send(CFG)
        if self.path == "/_last":
            return self._send(LAST)
        self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        LAST[self.path] = body
        if self.path == "/json/state":
            STATE.update({k: v for k, v in body.items() if k in ("on", "bri")})
            if body.get("seg"):
                STATE["seg"][0]["col"] = body["seg"][0]["col"]
        return self._send({"success": True})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
