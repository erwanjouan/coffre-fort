import os
import sys

from .crypto import decrypt, encrypt, read_password
from .keychain import get_password, store_password


def cmd_encrypt(src: str, dst: str) -> None:
    """
    Read a plaintext file, encrypt it, and write the result to a new file.

    This is the "lock the safe" command. It reads the source file as raw
    bytes, asks for a new password, encrypts everything, and writes the
    encrypted blob to the destination path with permissions 0o600 so that
    only the current user can read it.

    Args:
        src: Path to the plaintext file to encrypt (e.g. "secrets.yml").
        dst: Path where the encrypted output should be saved
             (e.g. "secrets.yml.enc").
    """
    with open(src, "rb") as f:
        plaintext = f.read()
    pw = get_password()
    ciphertext = encrypt(plaintext, pw)
    fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(ciphertext)
    print(f"encrypted → {dst}", file=sys.stderr)


def cmd_decrypt(src: str) -> None:
    """
    Decrypt an encrypted file and print its contents to the terminal.

    This is the "peek inside the safe" command. It reads the encrypted blob,
    asks for the password, decrypts, and writes the plaintext directly to
    stdout so you can pipe it to other tools (e.g. `| grep password`).
    Nothing is written to disk.

    Args:
        src: Path to the encrypted file (e.g. "secrets.yml.enc").
    """
    with open(src, "rb") as f:
        data = f.read()
    pw = get_password()
    plaintext = decrypt(data, pw)
    sys.stdout.buffer.write(plaintext)



def cmd_keychain_store() -> None:
    """Save the encryption password in the macOS Keychain with Touch ID protection.

    Run this once to register the password.  Every subsequent 'decrypt' will
    read from the Keychain and require a fingerprint scan instead of a typed
    password.
    """
    pw = read_password("Password to store in Keychain: ")
    store_password(pw)
    print("password stored in Keychain with Touch ID protection", file=sys.stderr)
