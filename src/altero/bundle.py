"""Where this altero runs from when it ships inside Altero.app.

The macOS app carries the Python engine as a nested helper app, built by
PyInstaller::

    Altero.app/                              host: widget container (Swift)
      Contents/Helpers/AlteroEngine.app/     this package, frozen
        Contents/MacOS/altero                CLI, TUI, menu bar, backend

Everything here answers "am I that engine, and where is it" from
``sys.frozen`` and ``sys.executable``, which PyInstaller sets with symlinks
already resolved, so a ``~/.local/bin/altero`` link into the app reads as the
app. A pip/uv install is never bundled, and every function here is then a
no-op, so shared code can call them unconditionally.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

from altero.exceptions import ClaudeSwitchError

ENGINE_APP_NAME = "AlteroEngine.app"
ENGINE_BUNDLE_ID = "com.fullcontextlabs.altero.engine"
# The host app's own id (widget/project.yml, AlteroWidgetHost's
# PRODUCT_BUNDLE_IDENTIFIER), not the nested engine's. This is what macOS
# should credit a LaunchAgent to, via AssociatedBundleIdentifiers.
HOST_BUNDLE_ID = "com.fullcontextlabs.altero"
RELEASES_URL = "https://github.com/FullContextLabs/Altero/releases/latest"
# On PATH on stock macOS (/etc/paths). Not /opt/homebrew/bin: Homebrew owns it.
SYSTEM_BIN = Path("/usr/local/bin")
ZPROFILE_MARKER = "# added by Altero"
ZPROFILE_PATH_LINE = 'export PATH="$HOME/.local/bin:$PATH"'


def engine_executable() -> Path | None:
    """The bundled engine's executable, or None when not running from an app."""
    if not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable)
    contents = exe.parent.parent
    if exe.parent.name != "MacOS" or contents.name != "Contents" or contents.parent.suffix != ".app":
        return None
    return exe


def is_bundled() -> bool:
    return engine_executable() is not None


def host_app() -> Path | None:
    """The Altero.app that contains this engine, when it is nested in one."""
    exe = engine_executable()
    if exe is None:
        return None
    helpers = exe.parents[2].parent  # .../Contents/Helpers
    if helpers.name != "Helpers" or helpers.parent.name != "Contents":
        return None
    app = helpers.parent.parent
    return app if app.suffix == ".app" else None


def relocation_problem(path: Path, home: Path | None = None) -> str | None:
    """Why ``path`` is no place to point a login service at, or None.

    A LaunchAgent records an absolute path and launchd runs it at every
    login. Three places look fine today and are gone tomorrow: the random
    App Translocation copy macOS runs a quarantined app from, the mounted
    disk image, and the Downloads folder the image usually came through.
    """
    text = str(path)
    if "/AppTranslocation/" in text:
        return "macOS is running it from a temporary copy (App Translocation)"
    if text.startswith("/Volumes/"):
        return "it is running from the disk image"
    if path.is_relative_to((home or Path.home()) / "Downloads"):
        return "it is running from the Downloads folder"
    return None


def require_installed_location(path: Path, home: Path | None = None) -> None:
    """Refuse, with the fix, when ``path`` would make a login service rot."""
    reason = relocation_problem(path, home)
    if reason is not None:
        raise ClaudeSwitchError(
            f"Altero can't set up its background services because {reason}. "
            "Move Altero.app to the Applications folder, open it from there, "
            "and try again."
        )


def _link_state(link: Path, exe: Path) -> str:
    """``current`` (already this app), ``free`` (missing, dangling, or a link
    into some Altero.app's engine) or ``foreign`` (anything else)."""
    if link.is_symlink():
        if os.path.realpath(link) == os.path.realpath(exe):
            return "current"
        if not link.exists() or ENGINE_APP_NAME in Path(os.readlink(link)).parts:
            return "free"
        return "foreign"
    return "foreign" if link.exists() else "free"


def _symlink(link: Path, exe: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    staging = link.parent / f".altero-{os.getpid()}.tmp"
    staging.unlink(missing_ok=True)
    staging.symlink_to(exe)
    os.replace(staging, link)


def _foreign(link: Path, hint: str) -> ClaudeSwitchError:
    return ClaudeSwitchError(
        f"{link} already exists and does not belong to Altero.app (a pip or "
        "uv install?), so it was left alone. Uninstall that one first "
        "(uv tool uninstall altero), then choose this again" + hint
    )


def _link_as_admin(link: Path, exe: Path) -> bool:
    """Create ``link`` through macOS's administrator prompt. False when the
    user cancels it or it fails."""
    command = (
        f"mkdir -p {shlex.quote(str(link.parent))} && "
        f"ln -sfh {shlex.quote(str(exe))} {shlex.quote(str(link))}"
    )
    applescript = command.replace("\\", "\\\\").replace('"', '\\"')
    try:
        result = subprocess.run(
            ["osascript", "-e", f'do shell script "{applescript}" with administrator privileges'],
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def _ensure_on_login_path(home: Path) -> None:
    """Put ``~/.local/bin`` on zsh's login PATH, once."""
    zprofile = home / ".zprofile"
    try:
        text = zprofile.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    if ZPROFILE_PATH_LINE in text:
        return
    separator = "\n" if text and not text.endswith("\n") else ""
    with zprofile.open("a", encoding="utf-8") as f:
        f.write(f"{separator}{ZPROFILE_MARKER}\n{ZPROFILE_PATH_LINE}\n")


def cli_tool_installed(home: Path | None = None) -> bool:
    """Whether ``altero`` in /usr/local/bin or ~/.local/bin is this app's."""
    exe = engine_executable()
    if exe is None:
        return False
    local = (home or Path.home()) / ".local" / "bin" / "altero"
    return any(_link_state(link, exe) == "current" for link in (SYSTEM_BIN / "altero", local))


def install_cli_tool(home: Path | None = None) -> str:
    """Symlink the app's ``altero`` into /usr/local/bin, which is on PATH.

    Links directly when /usr/local/bin is writable, otherwise through the
    administrator prompt. If that is cancelled or fails, falls back to
    ``~/.local/bin`` and adds it to PATH in ``~/.zprofile``.

    Returns what to tell the user. Never replaces an ``altero`` it did not
    put there: that is most likely a pip or uv install, and quietly shadowing
    it would change which build answers in every terminal. A dangling link,
    or one into an Altero.app (an older copy), is replaced.
    """
    exe = engine_executable()
    if exe is None:
        raise ClaudeSwitchError("The command line tool can only be installed from Altero.app.")
    require_installed_location(exe, home)
    home = home or Path.home()

    link = SYSTEM_BIN / "altero"
    state = _link_state(link, exe)
    if state == "current":
        return f"The command line tool is already installed at {link}."
    if state == "foreign":
        raise _foreign(link, ".")
    if SYSTEM_BIN.is_dir() and os.access(SYSTEM_BIN, os.W_OK):
        _symlink(link, exe)
        return f"Installed {link}. Open a new terminal and run `altero`."
    if _link_as_admin(link, exe):
        return f"Installed {link}. Open a new terminal and run `altero`."

    link = home / ".local" / "bin" / "altero"
    state = _link_state(link, exe)
    if state == "foreign":
        raise _foreign(
            link, f", or link the app's command yourself:\n  sudo ln -sf '{exe}' {SYSTEM_BIN}/altero"
        )
    if state == "free":
        _symlink(link, exe)
    _ensure_on_login_path(home)
    return (
        f"Couldn't link {SYSTEM_BIN}/altero, so installed {link} instead and added "
        f"{link.parent} to your PATH in ~/.zprofile. Open a new terminal to use `altero`."
    )
