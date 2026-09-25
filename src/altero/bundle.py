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


def install_cli_tool(target_dir: Path | None = None, home: Path | None = None) -> str:
    """Symlink the app's ``altero`` into ``target_dir`` (``~/.local/bin``).

    Returns what to tell the user. Never replaces an ``altero`` it did not
    put there: that is most likely a pip or uv install, and quietly shadowing
    it would change which build answers in every terminal. A dangling link
    (an app since moved or deleted) is replaced.
    """
    exe = engine_executable()
    if exe is None:
        raise ClaudeSwitchError("The command line tool can only be installed from Altero.app.")
    require_installed_location(exe, home)
    target_dir = target_dir or (home or Path.home()) / ".local" / "bin"
    link = target_dir / "altero"
    system_hint = f"  sudo ln -sf '{exe}' /usr/local/bin/altero"

    if link.is_symlink() and os.path.realpath(link) == os.path.realpath(exe):
        return f"The command line tool is already installed at {link}."
    if link.exists():
        raise ClaudeSwitchError(
            f"{link} already exists and does not belong to Altero.app (a pip or "
            "uv install?), so it was left alone. Uninstall that one first "
            "(uv tool uninstall altero), then choose this again, or link the "
            f"app's command somewhere else:\n{system_hint}"
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    staging = target_dir / f".altero-{os.getpid()}.tmp"
    staging.unlink(missing_ok=True)
    staging.symlink_to(exe)
    os.replace(staging, link)
    return (
        f"Installed {link}. If a new terminal cannot find `altero`, add "
        f"{target_dir} to your PATH, or link it system-wide instead:\n{system_hint}"
    )
