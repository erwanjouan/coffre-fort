# coffre-fort

A minimal command-line tool to store secrets in an encrypted YAML file and edit
them through a local browser-based editor.

## What it does

`coffre-fort` encrypts a YAML file containing passwords and credentials using
AES-256-GCM with an Argon2id-derived key. The encrypted file is safe to commit
to version control or store in the cloud. Secrets are only decrypted in memory —
nothing is ever written back to disk in plaintext.

On macOS, every operation is gated behind **Touch ID**: the master password is
stored in the macOS Keychain and is only released after a successful fingerprint
scan.

## Encryption

- **Algorithm:** AES-256-GCM (authenticated — detects any tampering or corruption)
- **Key derivation:** Argon2id (deliberately slow to resist brute-force attacks)
- **File format:** `MAGIC (8 B) | salt (32 B) | nonce (12 B) | ciphertext`

The `MAGIC` prefix (`SECRETS1`) lets the tool detect non-secrets files before
attempting decryption.

## Setup

```bash
make install          # create .venv and install dependencies
make keychain-store   # one-time: save the master password in the macOS Keychain
```

After `keychain-store`, every subsequent command will prompt for Touch ID instead
of asking you to type the password.

## Commands

| Command | What it does |
|---------|-------------|
| `make encrypt` | Encrypt `secrets.yml` → `secrets.yml.enc` |
| `make decrypt` | Decrypt `secrets.yml.enc` to stdout |
| `make serve`   | Start the web editor on http://127.0.0.1:9371 |

Override defaults with Make variables:

```bash
make encrypt SRC=other.yml ENC=other.yml.enc
make serve PORT=8080
```

Run directly without Make:

```bash
.venv/bin/python3 main.py <command> [args]
```

## Web editor (`make serve`)

`make serve` decrypts the secrets file once at startup, keeps the plaintext in
memory, and opens a local web editor in your browser.

- **CodeMirror** editor with YAML syntax highlighting and search (Ctrl+F / Cmd+F)
- **Manual save**: the Save button enables when you make a change; clicking it
  re-encrypts and writes the file to disk
- **Automatic backups**: before every save, the previous encrypted file is copied
  to `bak/<filename>.<YYYYMMDD_HHMMSS>` so you can always recover a prior version
- The server only accepts connections from `127.0.0.1` / `localhost` — it is not
  reachable from other machines on your network

## HTTP API

All endpoints are served by `make serve` on the same port.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web editor UI |
| `/api/yaml` | GET | Return the secrets as raw YAML text |
| `/api/yaml` | POST | Accept raw YAML, validate, backup and re-encrypt |
| `/api/secrets` | GET | Return the secrets as a JSON object |
| `/api/secrets` | POST | Accept a JSON object, backup and re-encrypt |
| `/api/get?category=&name=&property=` | GET | Return a single secret value |
| `/api/copy?category=&name=&property=` | GET | Copy a single value to the clipboard |

## Secrets YAML schema

```yaml
extra:
  - name: GitHub
    url: https://github.com
    login: username
    password: s3cr3t
    comment: optional note
```

Top-level keys are categories (e.g. `extra`, `work`). Each category contains a
list of entries. Each entry has at minimum a `name` field.

## Clipboard support

`/api/copy` uses the OS clipboard tool:

- macOS → `pbcopy`
- Windows → `clip`
- Linux → `xclip` (falls back to `xsel`)

## Project layout

```
coffre_fort/
    crypto.py    — AES-256-GCM + Argon2id encryption primitives
    keychain.py  — Touch ID gate (Swift/LAContext) + Keychain read/write
    clipboard.py — OS-specific clipboard copy
    files.py     — cmd_encrypt, cmd_decrypt
    api.py       — HTTP server, web editor backend
    cli.py       — argument parsing, entry point
    public/
        index.html   — web editor UI
        js/app.js    — CodeMirror editor, save logic
        js/api.js    — fetch helpers (loadYaml / saveYaml)
        schema.json  — JSON schema for the secrets structure
main.py              — thin entry point
```
