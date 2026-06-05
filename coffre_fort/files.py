import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

from .crypto import decrypt, encrypt, read_new_password, read_password


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
    pw = read_new_password()
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
    pw = read_password("Password: ")
    plaintext = decrypt(data, pw)
    sys.stdout.buffer.write(plaintext)


def cmd_edit(enc_file: str) -> None:
    """
    Open an encrypted file in a text editor, then re-encrypt it on save.

    This is the "edit without exposing secrets" command. The steps are:
      1. Decrypt the file into a temporary file (only readable by you).
      2. Open that temp file in your preferred editor ($EDITOR, default: vi).
      3. When you close the editor, read the (possibly changed) content.
      4. Re-encrypt with the same password.
      5. Back up the old encrypted file to the bak/ folder with a timestamp.
      6. Atomically replace the encrypted file with the new version.
      7. Delete the temporary plaintext file.

    The temp file is always cleaned up in a `finally` block, so it is
    removed even if an error occurs mid-way.

    If the encrypted file does not exist yet, the editor opens with an
    empty buffer and a fresh password is chosen — this is how you create
    a new secrets file.

    Args:
        enc_file: Path to the encrypted file to edit (e.g. "secrets.yml.enc").
    """
    if os.path.exists(enc_file):
        with open(enc_file, "rb") as f:
            data = f.read()
        pw = read_password("Password: ")
        plaintext = decrypt(data, pw)
    else:
        pw = read_new_password()
        plaintext = b""

    fd, tmp_path = tempfile.mkstemp(suffix=".yml")
    try:
        os.chmod(tmp_path, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(plaintext)

        editor = os.environ.get("EDITOR", "vi")
        result = subprocess.run([editor, tmp_path])
        if result.returncode != 0:
            raise RuntimeError(f"editor exited with code {result.returncode}")

        with open(tmp_path, "rb") as f:
            edited = f.read()

        ciphertext = encrypt(edited, pw)

        if os.path.exists(enc_file):
            bak_dir = os.path.join(os.path.dirname(os.path.abspath(enc_file)), "bak")
            os.makedirs(bak_dir, mode=0o700, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(enc_file, os.path.join(bak_dir, os.path.basename(enc_file) + "." + ts))

        tmp_out = enc_file + ".tmp"
        fd2 = os.open(tmp_out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd2, "wb") as f:
            f.write(ciphertext)
        os.rename(tmp_out, enc_file)
        print(f"saved → {enc_file}", file=sys.stderr)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
