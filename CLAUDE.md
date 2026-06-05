# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install          # create .venv and install dependencies
make encrypt          # encrypt secrets.yml → secrets.yml.enc (prompts for password)
make decrypt          # decrypt secrets.yml.enc to stdout
make edit             # open encrypted file in $EDITOR and re-encrypt on save
make serve            # start local HTTP API on port 9371
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
    clipboard.py — OS-specific clipboard copy (pbcopy / clip / xclip / xsel)
    files.py     — cmd_encrypt, cmd_decrypt, cmd_edit
    api.py       — cmd_serve, get_nested, HTTP request handler
    cli.py       — argument parsing, usage, main()
main.py          — entry point: from coffre_fort.cli import main
```

**Encryption scheme:** AES-256-GCM with Argon2id key derivation. Binary file layout: `MAGIC (8 bytes "SECRETS1") | salt (32 B) | nonce (12 B) | ciphertext`. The magic prefix allows detecting non-secrets files before attempting decryption.

**CLI commands map 1-to-1 to functions:**
- `encrypt` / `decrypt` — `cmd_encrypt` / `cmd_decrypt` in `files.py`: file I/O + crypto, writes output with mode `0o600`
- `edit` — `cmd_edit` in `files.py`: decrypt → write to `tempfile` (mode `0o600`) → open `$EDITOR` → re-encrypt → atomic rename; backs up previous `.enc` file to `bak/` with timestamp
- `serve` — `cmd_serve` in `api.py`: decrypts once at startup, holds secrets in memory, runs `HTTPServer` on `127.0.0.1`. Three endpoints: `GET /secrets` (full dump), `GET /get?key=<dotted.key>` (single value), `GET /copy?key=<dotted.key>` (copy to clipboard).

**Secrets YAML schema** (`secrets.yml`):
```yaml
extra:
  entry-key:
    name: Display Name
    url: https://...
    login: username
    mot de passe: password
```

**Clipboard support** (`coffre_fort/clipboard.py`): `pbcopy` on macOS, `clip` on Windows, `xclip`/`xsel` on Linux.

**No test suite exists.** Manual testing via the Make targets is the current workflow.
