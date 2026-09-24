"""Path resolution for Claude Code config and credential files.

Mirrors claude-code's own resolution so altero reads and writes the same files
claude-code does. Key rules (from claude-code source):

- Config home: ``CLAUDE_CONFIG_DIR`` if set, else ``~/.claude``.
- Global config: ``<config_home>/.config.json`` if it exists (legacy),
  otherwise ``(CLAUDE_CONFIG_DIR || $HOME)/.claude.json``. Note the asymmetry:
  ``.claude.json`` sits at homedir by default, not inside ``.claude/``.
- Credentials: ``<config_home>/.credentials.json``.

Also resolves the Altero data root, which on Linux/WSL follows the XDG Base
Directory Specification (``$XDG_DATA_HOME/altero``) and is ``~/.altero`` on
macOS/Windows.

References:
- claude-code utils/env.ts getGlobalClaudeFile
- claude-code utils/secureStorage/plainTextStorage.ts getStoragePath
- XDG Base Directory Specification: https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
"""

from __future__ import annotations

import os
from pathlib import Path

from altero.models import Platform

BACKUP_DIRNAME = ".altero"
XDG_DIRNAME = "altero"


def get_claude_config_home() -> Path:
    """Return the Claude config home directory (CLAUDE_CONFIG_DIR or ~/.claude)."""
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env)
    return Path.home() / ".claude"


def get_global_config_path() -> Path:
    """Return the path to the global Claude config file.

    Returns the legacy ``<config_home>/.config.json`` if it exists, else
    ``(CLAUDE_CONFIG_DIR || $HOME)/.claude.json``.
    """
    legacy = get_claude_config_home() / ".config.json"
    if legacy.exists():
        return legacy
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(env) if env else Path.home()
    return base / ".claude.json"


def get_default_claude_config_home() -> Path:
    """Return the *default* profile's config home, ignoring ``CLAUDE_CONFIG_DIR``.

    ``_read_capture_credentials`` has to tell an env var that names the default
    profile from one that names another, since only the former's credential is
    the active store's.
    """
    return Path.home() / ".claude"


def get_default_global_config_path() -> Path:
    """Return the global config path of the *default* profile.

    Same legacy fallback as :func:`get_global_config_path`, but deliberately
    ignores ``CLAUDE_CONFIG_DIR``: callers that mirror the user's real profile
    (session sharing) must not source from another session when invoked from
    inside one.
    """
    legacy = get_default_claude_config_home() / ".config.json"
    if legacy.exists():
        return legacy
    return Path.home() / ".claude.json"


def get_credentials_path() -> Path:
    """Return the path to the Claude credentials file."""
    return get_claude_config_home() / ".credentials.json"


def _xdg_data_home() -> Path:
    """``$XDG_DATA_HOME``, or ``~/.local/share`` when unset, empty or relative.

    A leading ``~`` is expanded so values like ``~/data`` set via systemd unit
    files or Dockerfiles (which don't get shell expansion) still work.
    """
    xdg = os.environ.get("XDG_DATA_HOME", "")
    if xdg:
        xdg_path = Path(os.path.expanduser(xdg))
        if xdg_path.is_absolute():
            return xdg_path
    return Path.home() / ".local" / "share"


def _uses_xdg() -> bool:
    return Platform.detect() in (Platform.LINUX, Platform.WSL)


def get_backup_root() -> Path:
    """Return the Altero data root for the current platform.

    Linux/WSL: ``$XDG_DATA_HOME/altero`` (default ``~/.local/share/altero``).
    macOS/Windows/unknown: ``~/.altero``.
    """
    if _uses_xdg():
        return _xdg_data_home() / XDG_DIRNAME
    return Path.home() / BACKUP_DIRNAME
