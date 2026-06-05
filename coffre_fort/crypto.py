import getpass
import os

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"SECRETS1"
SALT_LEN = 32
NONCE_LEN = 12
KEY_LEN = 32
ARGON_TIME = 3
ARGON_MEMORY = 64 * 1024
ARGON_THREADS = 4


def derive_key(password: bytes, salt: bytes) -> bytes:
    """
    Turn a human password into a fixed-size cryptographic key.

    Passwords are usually short and predictable, so we can't use them directly
    as encryption keys. This function runs the password through Argon2id, a
    deliberately slow algorithm, to make it much harder for an attacker to
    guess the password by brute force.

    Args:
        password: The user's password, already converted to raw bytes.
        salt:     A random sequence of bytes that was generated when the file
                  was first encrypted. Using a unique salt means the same
                  password produces a different key each time, which prevents
                  certain attacks.

    Returns:
        A 32-byte key suitable for AES-256 encryption.
    """
    return hash_secret_raw(
        secret=password,
        salt=salt,
        time_cost=ARGON_TIME,
        memory_cost=ARGON_MEMORY,
        parallelism=ARGON_THREADS,
        hash_len=KEY_LEN,
        type=Type.ID,
    )


def encrypt(plaintext: bytes, password: bytes) -> bytes:
    """
    Encrypt data using AES-256-GCM and return the full binary blob.

    The function generates fresh random bytes for the salt and nonce every
    time it is called, so encrypting the same data twice will produce
    different output — that's intentional and a good security property.

    The returned bytes are laid out as:
        MAGIC (8 B) | salt (32 B) | nonce (12 B) | ciphertext

    The MAGIC prefix lets us quickly detect whether a file is a valid secrets
    file before even trying to decrypt it.

    Args:
        plaintext: The raw bytes you want to protect (e.g. the YAML content).
        password:  The user's password as bytes, used to derive the key.

    Returns:
        A single bytes object containing the magic header, salt, nonce, and
        the authenticated ciphertext.
    """
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = derive_key(password, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return MAGIC + salt + nonce + ciphertext


def decrypt(data: bytes, password: bytes) -> bytes:
    """
    Decrypt a binary blob that was produced by `encrypt`.

    The function reads the salt and nonce from their fixed positions inside
    the blob, re-derives the key from the password, and then decrypts the
    ciphertext. AES-GCM also verifies an authentication tag, so any
    tampering with the file or a wrong password will be caught and raise
    an error — you will never silently get garbled output.

    Args:
        data:     The full encrypted blob (magic + salt + nonce + ciphertext).
        password: The user's password as bytes.

    Returns:
        The original plaintext bytes.

    Raises:
        ValueError: If the file is too short, the magic header is wrong, or
                    the password is incorrect / the file has been tampered with.
    """
    min_len = len(MAGIC) + SALT_LEN + NONCE_LEN
    if len(data) < min_len:
        raise ValueError("invalid encrypted file")
    if data[: len(MAGIC)] != MAGIC:
        raise ValueError("not a secrets file (wrong magic bytes)")

    off = len(MAGIC)
    salt = data[off : off + SALT_LEN]
    off += SALT_LEN
    nonce = data[off : off + NONCE_LEN]
    off += NONCE_LEN
    ciphertext = data[off:]

    key = derive_key(password, salt)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise ValueError("wrong password or corrupted file")


def read_password(prompt: str) -> bytes:
    """
    Ask the user to type a password without echoing it to the terminal.

    Uses Python's built-in `getpass` so the characters stay hidden while
    typing — you won't see asterisks or anything, which is normal.

    Args:
        prompt: The text shown to the user before they type, e.g. "Password: ".

    Returns:
        The typed password encoded as UTF-8 bytes.
    """
    return getpass.getpass(prompt).encode()


def read_new_password() -> bytes:
    """
    Ask the user to choose and confirm a new password.

    Prompts twice and checks that both entries match. This prevents typos
    from locking you out of a freshly encrypted file, because a typo you
    can't reproduce would make the data unrecoverable.

    Returns:
        The confirmed password encoded as UTF-8 bytes.

    Raises:
        ValueError: If the two entries don't match.
    """
    pw = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm password: ")
    if pw != confirm:
        raise ValueError("passwords do not match")
    return pw.encode()
