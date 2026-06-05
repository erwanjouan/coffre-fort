import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import yaml

from .clipboard import copy_to_clipboard
from .crypto import decrypt, read_password


def get_nested(data: dict, dotted_key: str):
    """
    Look up a value deep inside a nested dictionary using a dot-separated key.

    For example, given the dictionary {"extra": {"github": {"login": "alice"}}}
    and the key "extra.github.login", this function returns "alice".

    This lets the HTTP API reference any value in the secrets YAML with a
    simple string like "extra.github.mot de passe".

    Args:
        data:       A (possibly nested) dictionary, typically loaded from YAML.
        dotted_key: A key path where levels are separated by dots,
                    e.g. "extra.github.login".

    Returns:
        The value found at that path (could be a string, number, dict, etc.).

    Raises:
        KeyError: If any part of the path does not exist in the dictionary.
    """
    keys = dotted_key.split(".")
    node = data
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            raise KeyError(dotted_key)
        node = node[k]
    return node


def cmd_serve(enc_file: str, port: int) -> None:
    """
    Decrypt the secrets file once and serve them over a local HTTP API.

    This lets browser extensions or other local tools fetch secrets without
    ever touching the encrypted file themselves. The server only binds to
    127.0.0.1 (your machine, not the network), so external computers cannot
    reach it.

    Three endpoints are available:
      GET /secrets               — return the entire secrets dictionary as JSON.
      GET /get?key=a.b.c         — return a single value by dotted key.
      GET /copy?key=a.b.c        — copy a single value to the clipboard.

    Security notes:
      - The Host header is checked on every request to prevent DNS rebinding
        attacks (a technique where a malicious website tricks your browser into
        making requests to your local server).
      - CORS headers are set so only requests from http://127.0.0.1 or
        http://localhost are accepted by the browser.

    Args:
        enc_file: Path to the encrypted secrets file.
        port:     TCP port to listen on (default 9371).
    """
    with open(enc_file, "rb") as f:
        data = f.read()
    pw = read_password("Password: ")
    plaintext = decrypt(data, pw)
    secrets = yaml.safe_load(plaintext)

    _localhost_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"}

    def _is_localhost_origin(origin: str) -> bool:
        p = urlparse(origin)
        return p.scheme == "http" and p.hostname in ("127.0.0.1", "localhost")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            """Silence the default per-request log lines printed to stdout."""
            pass

        def _cors(self):
            """
            Add CORS headers to the current response.

            CORS (Cross-Origin Resource Sharing) is the browser mechanism that
            controls which websites are allowed to read responses from a server.
            Here we allow requests only from http://127.0.0.1 or
            http://localhost origins, and we set Access-Control-Allow-Private-
            Network so Chrome allows a public page to reach a localhost server.
            """
            origin = self.headers.get("Origin", "")
            if _is_localhost_origin(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")

        def _json(self, code: int, body) -> None:
            """
            Send an HTTP response with a JSON body.

            Serialises `body` to JSON, then writes the status line, CORS
            headers, Content-Type, Content-Length, and the payload in the
            correct order required by the HTTP protocol.

            Args:
                code: HTTP status code (200 = OK, 400 = bad request, etc.).
                body: Any Python object that can be serialised to JSON
                      (dict, list, string …).
            """
            payload = json.dumps(body).encode()
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _check_host(self) -> bool:
            """
            Reject the request if the Host header is not a localhost address.

            This guards against DNS rebinding: an attacker could register a
            domain that resolves to 127.0.0.1 and trick your browser into
            sending requests to this server. Checking the Host header means
            only requests explicitly addressed to 127.0.0.1 or localhost are
            processed.

            Returns:
                True if the host is acceptable; False if a 403 was sent.
            """
            host = self.headers.get("Host", "")
            if host not in _localhost_hosts:
                self._json(403, {"error": "forbidden: non-local host"})
                return False
            return True

        def do_OPTIONS(self):
            """
            Handle the HTTP OPTIONS pre-flight request sent by browsers.

            Before a browser makes a cross-origin GET request, it first sends
            an OPTIONS request to ask "is this allowed?". We respond with 204
            (No Content) plus the CORS headers so the browser proceeds with
            the actual GET.
            """
            if not self._check_host():
                return
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            """
            Handle all incoming GET requests and route them to the right action.

            Routes:
              /secrets          — return every secret as a JSON object.
              /get?key=…        — return the value at a specific dotted key.
              /copy?key=…       — copy the value at a specific dotted key to
                                  the clipboard and return {"ok": true}.
              anything else     — return a 404 JSON error.
            """
            if not self._check_host():
                return
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if parsed.path == "/secrets":
                self._json(200, secrets)

            elif parsed.path == "/copy":
                key = params.get("key", [None])[0]
                if not key:
                    self._json(400, {"error": "missing key parameter"})
                    return
                try:
                    value = get_nested(secrets, key)
                    copy_to_clipboard(str(value))
                    self._json(200, {"ok": True})
                except KeyError:
                    self._json(404, {"error": f"key not found: {key}"})
                except Exception as e:
                    self._json(500, {"error": str(e)})

            elif parsed.path == "/get":
                key = params.get("key", [None])[0]
                if not key:
                    self._json(400, {"error": "missing key parameter"})
                    return
                try:
                    value = get_nested(secrets, key)
                    self._json(200, {"key": key, "value": value})
                except KeyError:
                    self._json(404, {"error": f"key not found: {key}"})

            else:
                self._json(404, {"error": "not found"})

    server = HTTPServer(("127.0.0.1", port), Handler)
    base = f"http://127.0.0.1:{port}"
    print(f"serving on {base}", file=sys.stderr)
    print(f"  GET {base}/secrets", file=sys.stderr)
    print(f"  GET {base}/get?key=<dotted.key>", file=sys.stderr)
    print(f"  GET {base}/copy?key=<dotted.key>", file=sys.stderr)
    server.serve_forever()
