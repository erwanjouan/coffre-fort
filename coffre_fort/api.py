import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import yaml

from .clipboard import copy_to_clipboard
from .crypto import decrypt, encrypt
from .keychain import get_password

_PUBLIC = os.path.join(os.path.dirname(__file__), "public")

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js":   "application/javascript",
    ".json": "application/json",
    ".css":  "text/css",
}


def get_secret(data: dict, category: str, name: str, prop: str):
    cat = data.get(category)
    if not isinstance(cat, list):
        raise KeyError(f"category not found: {category}")
    item = next((el for el in cat if isinstance(el, dict) and el.get("name") == name), None)
    if item is None:
        raise KeyError(f"name not found: {name}")
    if prop not in item:
        raise KeyError(f"property not found: {prop}")
    return item[prop]


def cmd_serve(enc_file: str, port: int) -> None:
    with open(enc_file, "rb") as f:
        raw = f.read()
    pw = get_password()
    plaintext = decrypt(raw, pw)
    state = {"secrets": yaml.safe_load(plaintext)}

    _localhost_hosts = {
        f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"
    }

    def _is_local_origin(origin: str) -> bool:
        p = urlparse(origin)
        return p.scheme == "http" and p.hostname in ("127.0.0.1", "localhost")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _cors(self):
            origin = self.headers.get("Origin", "")
            if _is_local_origin(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")

        def _json(self, code: int, body) -> None:
            payload = json.dumps(body).encode()
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _static(self, rel_path: str) -> None:
            full = os.path.realpath(os.path.join(_PUBLIC, rel_path.lstrip("/")))
            if not full.startswith(_PUBLIC) or not os.path.isfile(full):
                self._json(404, {"error": "not found"})
                return
            ext = os.path.splitext(full)[1]
            with open(full, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", _MIME.get(ext, "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _check_host(self) -> bool:
            if self.headers.get("Host", "") not in _localhost_hosts:
                self._json(403, {"error": "forbidden: non-local host"})
                return False
            return True

        def do_OPTIONS(self):
            if not self._check_host():
                return
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            if not self._check_host():
                return
            parsed = urlparse(self.path)
            path   = parsed.path
            params = parse_qs(parsed.query)

            if path in ("/", "/index.html"):
                self._static("index.html")
            elif path.startswith("/js/"):
                self._static(path)
            elif path == "/api/secrets":
                self._json(200, state["secrets"])
            elif path == "/api/schema":
                with open(os.path.join(_PUBLIC, "schema.json")) as f:
                    self._json(200, json.load(f))
            elif path == "/api/get":
                category = params.get("category", [None])[0]
                name     = params.get("name",     [None])[0]
                prop     = params.get("property", [None])[0]
                if not category or not name or not prop:
                    self._json(400, {"error": "missing category, name, or property parameter"})
                    return
                try:
                    value = get_secret(state["secrets"], category, name, prop)
                    self._json(200, {"category": category, "name": name, "property": prop, "value": value})
                except KeyError as e:
                    self._json(404, {"error": str(e)})
            elif path == "/api/copy":
                category = params.get("category", [None])[0]
                name     = params.get("name",     [None])[0]
                prop     = params.get("property", [None])[0]
                if not category or not name or not prop:
                    self._json(400, {"error": "missing category, name, or property parameter"})
                    return
                try:
                    copy_to_clipboard(str(get_secret(state["secrets"], category, name, prop)))
                    self._json(200, {"ok": True})
                except KeyError as e:
                    self._json(404, {"error": str(e)})
                except Exception as e:
                    self._json(500, {"error": str(e)})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            if not self._check_host():
                return
            if urlparse(self.path).path != "/api/secrets":
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                new_secrets = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, ValueError):
                self._json(400, {"error": "invalid JSON"})
                return
            new_plain = yaml.dump(new_secrets, allow_unicode=True, default_flow_style=False).encode()
            fd = os.open(enc_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(encrypt(new_plain, pw))
            state["secrets"] = new_secrets
            self._json(200, {"ok": True})

    url = f"http://127.0.0.1:{port}"
    print(f"serving editor on {url}", file=sys.stderr)
    webbrowser.open(url)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
