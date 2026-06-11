import sys

from .api import cmd_serve
from .files import cmd_decrypt, cmd_encrypt, cmd_keychain_store


def usage():
    """
    Print a short help message explaining all available commands.

    Called automatically when the user runs the program with no arguments
    or with an unknown command. Output goes to stderr (the error stream)
    so it does not pollute stdout, which may be piped to another program.
    """
    print(
        """\
Usage:
  coffre-fort encrypt        <plaintext> <output>   encrypt a plaintext file (Touch ID)
  coffre-fort decrypt        <encrypted-file>        decrypt to stdout (Touch ID)
  coffre-fort serve          <encrypted-file> [port] run local HTTP API (default port 9371)
  coffre-fort keychain-store                         save password in Keychain (Touch ID)

Examples:
  coffre-fort keychain-store                         # one-time setup
  coffre-fort encrypt        secrets.yml secrets.yml.enc
  coffre-fort decrypt        secrets.yml.enc
  coffre-fort serve          secrets.yml.enc
  coffre-fort serve          secrets.yml.enc 8080
""",
        file=sys.stderr,
    )


def main():
    """
    Entry point: parse command-line arguments and call the right command.

    Reads sys.argv (the list of words the user typed after the program name),
    figures out which command was requested, validates that the right number
    of arguments was provided, and delegates to the matching function.

    Any exception raised by a command is caught here so the program always
    exits cleanly with a readable error message instead of a Python traceback.
    Exit code 1 signals failure to the shell (e.g. so Make knows the target
    failed).
    """
    args = sys.argv[1:]
    if not args:
        usage()
        sys.exit(1)

    cmd = args[0]
    try:
        if cmd == "encrypt":
            if len(args) != 3:
                print("usage: coffre-fort encrypt <src> <dst>", file=sys.stderr)
                sys.exit(1)
            cmd_encrypt(args[1], args[2])
        elif cmd == "decrypt":
            if len(args) != 2:
                print("usage: coffre-fort decrypt <file>", file=sys.stderr)
                sys.exit(1)
            cmd_decrypt(args[1])
        elif cmd == "keychain-store":
            if len(args) != 1:
                print("usage: coffre-fort keychain-store", file=sys.stderr)
                sys.exit(1)
            cmd_keychain_store()
        elif cmd == "serve":
            if len(args) < 2 or len(args) > 3:
                print("usage: coffre-fort serve <file> [port]", file=sys.stderr)
                sys.exit(1)
            port = int(args[2]) if len(args) == 3 else 9371
            cmd_serve(args[1], port)
        else:
            usage()
            sys.exit(1)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
