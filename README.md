# coffre-fort

A minimal command-line tool to store secrets in an encrypted file and optionally
expose them through a local HTTP API.

## What it does

`coffre-fort` encrypts a YAML file containing passwords and credentials using
AES-256-GCM with an Argon2id-derived key. The encrypted file is safe to commit
to version control or store in the cloud. Secrets are only decrypted in memory —
nothing is written back to disk in plaintext.

## Encryption

- **Algorithm:** AES-256-GCM (authenticated — detects any tampering)
- **Key derivation:** Argon2id (slow by design to resist brute-force attacks)
- **File format:** `MAGIC | salt (32 B) | nonce (12 B) | ciphertext`

## Commands

| Command | What it does |
|---------|-------------|
| `make encrypt` | Encrypt `secrets.yml` → `secrets.yml.enc` |
| `make decrypt` | Decrypt to stdout |
| `make edit`    | Open in `$EDITOR`, re-encrypt on save |
| `make serve`   | Start a local HTTP API on port 9371 |

## HTTP API (serve mode)

| Endpoint | Description |
|----------|-------------|
| `GET /secrets` | Return all secrets as JSON |
| `GET /get?key=a.b.c` | Return a single value by dotted key |
| `GET /copy?key=a.b.c` | Copy a value to the clipboard |
