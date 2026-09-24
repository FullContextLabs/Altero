"""Tests for altero.paths resolver helpers.

These tests verify that altero resolves Claude Code config/credential paths the
same way claude-code itself does. If these drift from claude-code's behavior,
altero will read the wrong files and misattribute accounts.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from altero.models import Platform
from altero.paths import (
    get_backup_root,
    get_claude_config_home,
    get_credentials_path,
    get_global_config_path,
)


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Temp HOME with CLAUDE_CONFIG_DIR unset."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    with patch("pathlib.Path.home", return_value=home):
        yield home


class TestGetClaudeConfigHome:
    def test_default_is_dot_claude_in_home(self, isolated_home: Path):
        assert get_claude_config_home() == isolated_home / ".claude"

    def test_respects_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        custom = tmp_path / "custom-claude"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
        assert get_claude_config_home() == custom


class TestGetGlobalConfigPath:
    def test_default_returns_homedir_claude_json(self, isolated_home: Path):
        """Without CCD, claude-code writes .claude.json at $HOME, not inside .claude/."""
        assert get_global_config_path() == isolated_home / ".claude.json"

    def test_ccd_set_returns_ccd_claude_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        custom = tmp_path / "ccd"
        custom.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
        assert get_global_config_path() == custom / ".claude.json"

    def test_legacy_config_json_takes_precedence(self, isolated_home: Path):
        """If ~/.claude/.config.json exists, claude-code uses that (legacy)."""
        config_home = isolated_home / ".claude"
        config_home.mkdir(exist_ok=True)
        legacy = config_home / ".config.json"
        legacy.write_text("{}")
        assert get_global_config_path() == legacy

    def test_legacy_config_json_in_ccd_takes_precedence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        custom = tmp_path / "ccd"
        custom.mkdir()
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
        legacy = custom / ".config.json"
        legacy.write_text("{}")
        assert get_global_config_path() == legacy


class TestGetCredentialsPath:
    def test_default_inside_dot_claude(self, isolated_home: Path):
        assert get_credentials_path() == isolated_home / ".claude" / ".credentials.json"

    def test_respects_ccd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        custom = tmp_path / "ccd"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom))
        assert get_credentials_path() == custom / ".credentials.json"


class TestGetBackupRoot:
    """Linux/WSL: XDG-aware path. Other platforms: ~/.altero."""

    def test_linux_default_is_xdg_data_home(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setattr(Platform, "detect", staticmethod(lambda: Platform.LINUX))
        assert get_backup_root() == isolated_home / ".local" / "share" / "altero"

    def test_linux_respects_xdg_data_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        custom = tmp_path / "xdg"
        monkeypatch.setenv("XDG_DATA_HOME", str(custom))
        monkeypatch.setattr(Platform, "detect", staticmethod(lambda: Platform.LINUX))
        assert get_backup_root() == custom / "altero"

    def test_linux_ignores_empty_xdg_data_home(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("XDG_DATA_HOME", "")
        monkeypatch.setattr(Platform, "detect", staticmethod(lambda: Platform.LINUX))
        assert get_backup_root() == isolated_home / ".local" / "share" / "altero"

    def test_linux_ignores_relative_xdg_data_home(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Per the XDG spec, relative paths must be ignored.
        monkeypatch.setenv("XDG_DATA_HOME", "relative/path")
        monkeypatch.setattr(Platform, "detect", staticmethod(lambda: Platform.LINUX))
        assert get_backup_root() == isolated_home / ".local" / "share" / "altero"

    def test_linux_expands_tilde_in_xdg_data_home(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # systemd unit files / Dockerfiles set env vars without shell
        # expansion, so a literal ``~/foo`` must still resolve correctly.
        monkeypatch.setenv("XDG_DATA_HOME", "~/custom-data")
        monkeypatch.setattr(Platform, "detect", staticmethod(lambda: Platform.LINUX))
        assert get_backup_root() == isolated_home / "custom-data" / "altero"

    def test_wsl_uses_xdg_layout(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setattr(Platform, "detect", staticmethod(lambda: Platform.WSL))
        assert get_backup_root() == isolated_home / ".local" / "share" / "altero"

    def test_macos_uses_dot_altero(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(Platform, "detect", staticmethod(lambda: Platform.MACOS))
        assert get_backup_root() == isolated_home / ".altero"

    def test_windows_uses_dot_altero(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(Platform, "detect", staticmethod(lambda: Platform.WINDOWS))
        assert get_backup_root() == isolated_home / ".altero"
