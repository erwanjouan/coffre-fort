# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install          # create .venv and install dependencies
make encrypt          # encrypt secrets.yml → secrets.yml.enc (prompts for password)
make decrypt          # decrypt secrets.yml.enc to stdout
make serve            # start local HTTP API + web editor on port 9371
```

Override defaults with Make variables: `make encrypt SRC=other.yml ENC=other.yml.enc`, `make serve PORT=8080`.

Run directly without Make:
```bash
.venv/bin/python3 main.py <command> [args]
```

## Architecture

The tool is structured as a `coffre_fort/` package. `main.py` is a thin entry point that delegates to `coffre_fort.cli.main`.

**Package layout:**
```
coffre_fort/
    crypto.py    — AES-256-GCM + Argon2id primitives, password prompts
    keychain.py  — Touch ID gate (Swift/LAContext) + Keychain read/write (Security framework via ctypes)
    clipboard.py — OS-specific clipboard copy (pbcopy / clip / xclip / xsel)
    files.py     — cmd_encrypt, cmd_decrypt
    api.py       — cmd_serve, get_secret, _backup, HTTP request handler
    cli.py       — argument parsing, usage, main()
    public/
        index.html        — web editor UI (CodeMirror 5, dark theme)
        js/app.js         — editor init, manual save, status display
        js/api.js         — loadYaml() / saveYaml() fetch helpers
        schema.json       — JSON schema for secrets structure
main.py          — entry point: from coffre_fort.cli import main
```

**Encryption scheme:** AES-256-GCM with Argon2id key derivation. Binary file layout: `MAGIC (8 bytes "SECRETS1") | salt (32 B) | nonce (12 B) | ciphertext`. The magic prefix allows detecting non-secrets files before attempting decryption.

**CLI commands map 1-to-1 to functions:**
- `encrypt` / `decrypt` — `cmd_encrypt` / `cmd_decrypt` in `files.py`: file I/O + crypto, writes output with mode `0o600`
- `serve` — `cmd_serve` in `api.py`: decrypts once at startup, holds secrets in memory (parsed dict + raw YAML string), runs `HTTPServer` on `127.0.0.1`, opens the web editor in the browser.

**HTTP API endpoints:**
- `GET /` — serves the CodeMirror web editor (`public/index.html`)
- `GET /api/yaml` — returns the raw YAML plaintext (`text/plain`)
- `POST /api/yaml` — accepts raw YAML, validates with `yaml.safe_load`, backs up the current `.enc` to `bak/<file>.<YYYYMMDD_HHMMSS>`, then re-encrypts and writes to disk
- `GET /api/secrets` — returns secrets as JSON
- `POST /api/secrets` — accepts JSON, same backup + re-encrypt flow
- `GET /api/get?category=&name=&property=` — returns a single secret value
- `GET /api/copy?category=&name=&property=` — copies a value to the clipboard

**Web editor** (`public/`): CodeMirror 5 loaded from cdnjs (UMD bundles — do not use esm.sh for CodeMirror). Editing is raw YAML with YAML syntax highlighting and search (Ctrl+F). Save is manual: the button enables on any change and POSTs to `/api/yaml` on click.

**Secrets YAML schema** (`secrets.yml`):
```yaml
extra:
  entry-key:
    name: Display Name
    url: https://...
    login: username
    mot de passe: password
```

**Touch ID / Keychain** (`coffre_fort/keychain.py`, macOS only):

Every command that needs the master password calls `get_password()`, which:
1. Runs an inline Swift snippet via `swift -` that calls `LAContext.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics)` — this triggers the Touch ID prompt. No entitlement is required.
2. On success, reads the password from the macOS Keychain using the Security framework directly via `ctypes` (no subprocess, no `security` CLI). The item is stored under service `"coffre-fort"` / account `"coffre-fort"` as a `kSecClassGenericPassword`.

`store_password()` (called by `make keychain-store`) writes the password into the Keychain: it deletes any existing entry first (`SecItemDelete`), then inserts the new one (`SecItemAdd`). One-time setup — after that every decrypt/serve/encrypt uses Touch ID.

The password is never written to disk in plaintext and never passed as a command-line argument.

**Clipboard support** (`coffre_fort/clipboard.py`): `pbcopy` on macOS, `clip` on Windows, `xclip`/`xsel` on Linux.

**No test suite exists.** Manual testing via the Make targets is the current workflow.
