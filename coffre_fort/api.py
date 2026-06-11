import json
import os
import shutil
import sys
from datetime import datetime
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
    """
    Look up a single property inside the secrets dictionary.

    The secrets file is organised as: category → list of entries → properties.
    For example, to get the password of the "GitHub" entry in the "extra"
    category you would call get_secret(data, "extra", "GitHub", "password").

    Args:
        data:     The full secrets dictionary loaded from the YAML file.
        category: The top-level group name (e.g. "extra", "work").
        name:     The value of the "name" field inside an entry (e.g. "GitHub").
        prop:     The property you want (e.g. "password", "login", "url").

    Returns:
        The value stored at that property (usually a string).

    Raises:
        KeyError: If the category, name, or property does not exist.
    """
    cat = data.get(category)
    if not isinstance(cat, list):
        raise KeyError(f"category not found: {category}")
    item = next((el for el in cat if isinstance(el, dict) and el.get("name") == name), None)
    if item is None:
        raise KeyError(f"name not found: {name}")
    if prop not in item:
        raise KeyError(f"property not found: {prop}")
    return item[prop]


def _backup(enc_file: str) -> None:
    """
    Copy the current encrypted file into a timestamped backup before overwriting it.

    Every time the editor saves, we call this function first so you always have
    a way to recover the previous version.  Backups are stored next to the
    encrypted file in a 'bak/' folder, with the date and time appended to the
    filename so they never collide.

    Example: 'secrets.yml.enc' → 'bak/secrets.yml.enc.20240611_143022'

    Args:
        enc_file: Path to the encrypted file that is about to be overwritten.
                  If the file does not exist yet (first ever save), this
                  function does nothing.
    """
    if not os.path.exists(enc_file):
        return
    bak_dir = os.path.join(os.path.dirname(os.path.abspath(enc_file)), "bak")
    os.makedirs(bak_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(enc_file, os.path.join(bak_dir, os.path.basename(enc_file) + "." + ts))


def cmd_serve(enc_file: str, port: int) -> None:
    """
    Decrypt the secrets file once, then run a local web server with the editor.

    This is the main "edit your secrets" command.  Here is what happens:

    1. The encrypted file is read from disk and decrypted in memory using your
       Touch ID-protected password.  The plaintext is never written back to disk.
    2. A tiny HTTP server starts on 127.0.0.1 (localhost only — not reachable
       from other machines on your network).
    3. Your browser opens automatically at http://127.0.0.1:<port>.
    4. The browser loads the CodeMirror editor, which talks to this server via
       fetch() calls to read and write the YAML.

    The server keeps the decrypted secrets in a 'state' dictionary in memory
    for the lifetime of the process.  When you save in the browser, the server
    re-encrypts everything and writes the new file to disk.

    Args:
        enc_file: Path to the encrypted secrets file (e.g. "secrets.yml.enc").
        port:     TCP port to listen on (default 9371).
    """
    with open(enc_file, "rb") as f:
        raw = f.read()
    pw = get_password()
    plaintext = decrypt(raw, pw)
    state = {"secrets": yaml.safe_load(plaintext), "yaml_raw": plaintext.decode("utf-8")}

    _localhost_hosts = {
        f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"
    }

    def _is_local_origin(origin: str) -> bool:
        p = urlparse(origin)
        return p.scheme == "http" and p.hostname in ("127.0.0.1", "localhost")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            """
            Silence the default request logging that Python's HTTP server prints.

            By default, BaseHTTPRequestHandler prints a line to the terminal for
            every request (e.g. "127.0.0.1 - GET /api/yaml 200").  Overriding
            this method with 'pass' (do nothing) keeps the terminal clean.
            """
            pass

        def _cors(self):
            """
            Add Cross-Origin Resource Sharing (CORS) headers to the current response.

            CORS is a browser security feature: by default, a web page can only
            make fetch() calls back to the exact server it was loaded from.  Our
            browser page is loaded from 127.0.0.1, so it can already talk to our
            server — but we still set these headers explicitly so browsers do not
            block the requests.

            We only echo back the 'Access-Control-Allow-Origin' header when the
            request comes from a localhost origin, so pages on other sites cannot
            use your browser to silently query the server.
            """
            origin = self.headers.get("Origin", "")
            if _is_local_origin(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")

        def _json(self, code: int, body) -> None:
            """
            Send an HTTP response whose body is a JSON object.

            JSON (JavaScript Object Notation) is the standard format for
            exchanging data between a server and a browser.  This helper
            serialises any Python dict or list into a JSON string, sets the
            correct Content-Type header so the browser knows what it is
            receiving, and writes it all to the network connection.

            Args:
                code: The HTTP status code to send (e.g. 200 = OK,
                      400 = bad request, 404 = not found, 500 = server error).
                body: Any Python object that can be serialised to JSON
                      (dict, list, string, number, bool).
            """
            payload = json.dumps(body).encode()
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _static(self, rel_path: str) -> None:
            """
            Serve a static file (HTML, JS, CSS) from the 'public/' directory.

            When the browser first loads the editor, it requests 'index.html' and
            then 'js/app.js'.  This method reads those files from disk and sends
            them as-is to the browser, with the right Content-Type header so the
            browser knows whether it is receiving HTML, JavaScript, or CSS.

            The path is validated against the public directory to prevent
            directory traversal attacks (e.g. a request for '../../secrets' that
            tries to escape the public folder).

            Args:
                rel_path: The URL path requested by the browser (e.g. '/js/app.js').
            """
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
            """
            Reject any request that did not come from localhost.

            The HTTP 'Host' header tells us which hostname the browser used to
            reach this server.  We only accept requests addressed to 127.0.0.1
            or localhost, so a malicious web page on a different site cannot
            trick your browser into talking to our server via a technique called
            DNS rebinding.

            Returns:
                True if the Host header is acceptable, False if the request was
                already rejected with a 403 Forbidden response.
            """
            if self.headers.get("Host", "") not in _localhost_hosts:
                self._json(403, {"error": "forbidden: non-local host"})
                return False
            return True

        def do_OPTIONS(self):
            """
            Handle an HTTP OPTIONS request (the CORS preflight check).

            Before a browser sends a real POST request, it first sends a cheap
            OPTIONS request to ask "are you willing to accept this?".  This is
            called a CORS preflight.  We simply reply with the CORS headers and
            a 204 No Content status so the browser knows it is allowed to
            proceed with the real request.
            """
            if not self._check_host():
                return
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            """
            Handle all HTTP GET requests from the browser.

            GET requests are read-only requests — the browser is asking for data
            without changing anything.  This method inspects the URL path and
            routes the request to the right response:

            - '/' or '/index.html'     → send the editor HTML page
            - '/js/*'                  → send a JavaScript file
            - '/api/yaml'              → send the raw YAML text of the secrets
            - '/api/secrets'           → send the secrets as a JSON object
            - '/api/schema'            → send the JSON schema definition
            - '/api/get?...'           → look up and return one secret value
            - '/api/copy?...'          → copy one secret value to the clipboard
            """
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
            elif path == "/api/yaml":
                payload = state["yaml_raw"].encode("utf-8")
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
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
            """
            Handle all HTTP POST requests from the browser.

            POST requests carry a body — the browser is sending data to the server
            to be stored or processed.  This method handles two routes:

            - '/api/yaml'     → the browser sends updated YAML text; we validate
                                it, back up the current file, re-encrypt, and save.
            - '/api/secrets'  → the browser sends a JSON object; same process
                                but starting from JSON instead of YAML.

            Any other path returns a 404 Not Found response.
            """
            if not self._check_host():
                return
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", 0))
            if path == "/api/yaml":
                raw_yaml = self.rfile.read(length).decode("utf-8")
                try:
                    new_secrets = yaml.safe_load(raw_yaml)
                except yaml.YAMLError as e:
                    self._json(400, {"error": f"invalid YAML: {e}"})
                    return
                _backup(enc_file)
                fd = os.open(enc_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(encrypt(raw_yaml.encode("utf-8"), pw))
                state["secrets"] = new_secrets
                state["yaml_raw"] = raw_yaml
                self._json(200, {"ok": True})
            elif path == "/api/secrets":
                try:
                    new_secrets = json.loads(self.rfile.read(length))
                except (json.JSONDecodeError, ValueError):
                    self._json(400, {"error": "invalid JSON"})
                    return
                new_yaml = yaml.dump(new_secrets, allow_unicode=True, default_flow_style=False)
                _backup(enc_file)
                fd = os.open(enc_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(encrypt(new_yaml.encode("utf-8"), pw))
                state["secrets"] = new_secrets
                state["yaml_raw"] = new_yaml
                self._json(200, {"ok": True})
            else:
                self._json(404, {"error": "not found"})

    url = f"http://127.0.0.1:{port}"
    print(f"serving editor on {url}", file=sys.stderr)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
