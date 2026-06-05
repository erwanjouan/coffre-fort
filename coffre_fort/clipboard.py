import platform
import subprocess


def copy_to_clipboard(text: str) -> None:
    """
    Copy a piece of text to the system clipboard.

    Different operating systems expose the clipboard through different command-
    line tools, so this function checks which OS is running and uses the right
    one automatically:
      - macOS  → pbcopy
      - Windows → clip
      - Linux  → xclip (falls back to xsel if xclip is not installed)

    Args:
        text: The string you want to place on the clipboard (e.g. a password).

    Raises:
        RuntimeError: If the current OS is not supported.
        subprocess.CalledProcessError: If the clipboard tool returns an error.
    """
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["pbcopy"], input=text.encode(), check=True)
    elif system == "Windows":
        subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True)
    elif system == "Linux":
        try:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        except FileNotFoundError:
            subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode(), check=True)
    else:
        raise RuntimeError(f"clipboard not supported on {system}")
