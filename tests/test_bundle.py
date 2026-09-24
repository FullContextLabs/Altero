"""Altero.app awareness: the frozen engine, the service pin, the refusals.

A frozen engine is simulated by laying out the app's directory tree under
``tmp_path`` and pointing ``sys.frozen``/``sys.executable`` at it, which is
all ``altero.bundle`` reads. ``launchctl`` is never run: ``subprocess.run`` is
patched wherever a service would be touched, and ``home`` is always a tmp
path.
"""

from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from altero import __version__, bundle, launch_agent, menubar, update_check
from altero.exceptions import ClaudeSwitchError
from altero.settings import load_service_settings, set_setting

# Altero.app is macOS-only. These build its directory tree with symlinks and
# exec bits and assert POSIX paths, none of which mean the same on Windows.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="Altero.app and its services are macOS-only"
)

UID = 501
ENGINE_REL = Path("Contents/Helpers/AlteroEngine.app/Contents/MacOS/altero")


def _executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def _freeze(monkeypatch, app: Path) -> Path:
    """Make this process look like the engine inside ``app``."""
    exe = _executable(app / ENGINE_REL)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    return exe


@pytest.fixture(autouse=True)
def _on_macos(tmp_path, monkeypatch):
    monkeypatch.setattr(launch_agent.sys, "platform", "darwin")
    monkeypatch.delenv(launch_agent.WIDGET_APP_ENV, raising=False)
    monkeypatch.setattr(launch_agent, "SYSTEM_APPLICATIONS", tmp_path / "system-Applications")
    launch_agent._program_versions.clear()


@pytest.fixture
def backup_root() -> Path:
    from altero import paths

    root = paths.get_backup_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _launchctl_ok(argv, **kwargs):
    return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")


class TestDetection:
    def test_a_pip_install_is_not_bundled(self):
        assert not bundle.is_bundled()
        assert bundle.engine_executable() is None
        assert bundle.host_app() is None

    def test_the_nested_engine_knows_its_host(self, tmp_path, monkeypatch):
        exe = _freeze(monkeypatch, tmp_path / "Applications" / "Altero.app")
        assert bundle.engine_executable() == exe
        assert bundle.host_app() == tmp_path / "Applications" / "Altero.app"

    def test_frozen_outside_an_app_is_not_bundled(self, tmp_path, monkeypatch):
        # A plain onedir build: frozen, but no bundle id and no Info.plist.
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(_executable(tmp_path / "dist" / "altero")))
        assert not bundle.is_bundled()

    def test_a_standalone_engine_app_has_no_host(self, tmp_path, monkeypatch):
        exe = _executable(tmp_path / "AlteroEngine.app" / "Contents" / "MacOS" / "altero")
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(exe))
        assert bundle.is_bundled()
        assert bundle.host_app() is None


class TestRelocation:
    @pytest.mark.parametrize(
        "path, fragment",
        [
            ("/private/var/folders/x/T/AppTranslocation/ABC/d/Altero.app", "App Translocation"),
            ("/Volumes/Altero/Altero.app", "disk image"),
        ],
    )
    def test_temporary_places_are_refused(self, path, fragment, tmp_path):
        assert fragment in bundle.relocation_problem(Path(path), home=tmp_path)
        with pytest.raises(ClaudeSwitchError, match="Move Altero.app to the Applications folder"):
            bundle.require_installed_location(Path(path), home=tmp_path)

    def test_downloads_is_refused(self, tmp_path):
        app = tmp_path / "Downloads" / "Altero.app"
        assert "Downloads" in bundle.relocation_problem(app, home=tmp_path)

    @pytest.mark.parametrize("path", ["/Applications/Altero.app", "/Users/x/Applications/Altero.app"])
    def test_applications_is_fine(self, path, tmp_path):
        assert bundle.relocation_problem(Path(path), home=tmp_path) is None


class TestServiceProgram:
    def test_without_a_pin_every_altero_installs_itself(self, backup_root):
        with patch.object(launch_agent, "resolve_program", return_value=["/dev/altero"]):
            assert launch_agent.service_program() == (["/dev/altero"], __version__)

    def test_the_engine_is_always_its_own_program(self, tmp_path, monkeypatch, backup_root):
        exe = _freeze(monkeypatch, tmp_path / "Applications" / "Altero.app")
        set_setting(backup_root, "service.program", str(_executable(tmp_path / "other" / "altero")))
        assert launch_agent.resolve_program() == [str(exe)]
        assert launch_agent.service_program() == ([str(exe)], __version__)

    def test_the_engine_refuses_to_serve_from_a_disk_image(self, tmp_path, monkeypatch):
        _freeze(monkeypatch, tmp_path / "AppTranslocation" / "X" / "Altero.app")
        with pytest.raises(ClaudeSwitchError, match="Applications"):
            launch_agent.service_program()

    def test_a_client_defers_to_the_pin(self, tmp_path, backup_root):
        pinned = _executable(tmp_path / "Altero.app" / ENGINE_REL)
        set_setting(backup_root, "service.program", str(pinned))
        with patch.object(launch_agent, "resolve_program", return_value=["/uv/altero"]), \
             patch.object(launch_agent, "program_version", return_value="9.9.9"):
            assert launch_agent.service_program() == ([str(pinned)], "9.9.9")

    def test_a_pin_that_is_gone_is_ignored(self, tmp_path, backup_root):
        # The app was deleted or moved: its services are dead either way, so
        # the altero at hand takes them over.
        set_setting(backup_root, "service.program", str(tmp_path / "deleted" / "altero"))
        with patch.object(launch_agent, "resolve_program", return_value=["/uv/altero"]):
            assert launch_agent.service_program() == (["/uv/altero"], __version__)

    def test_a_pin_on_oneself_is_oneself(self, tmp_path, backup_root):
        own = _executable(tmp_path / "bin" / "altero")
        set_setting(backup_root, "service.program", str(own))
        with patch.object(launch_agent, "resolve_program", return_value=[str(own)]), \
             patch.object(launch_agent, "program_version") as version:
            assert launch_agent.service_program() == ([str(own)], __version__)
        version.assert_not_called()


class TestProgramVersion:
    def test_reads_the_last_word_and_caches(self, tmp_path):
        exe = _executable(tmp_path / "altero")
        done = subprocess.CompletedProcess([], 0, stdout="altero 1.2.3\n", stderr="")
        with patch.object(launch_agent.subprocess, "run", return_value=done) as run:
            assert launch_agent.program_version([str(exe)]) == "1.2.3"
            assert launch_agent.program_version([str(exe)]) == "1.2.3"
        run.assert_called_once()

    def test_unknown_when_it_fails(self, tmp_path):
        exe = _executable(tmp_path / "altero")
        with patch.object(launch_agent.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 5)):
            assert launch_agent.program_version([str(exe)]) is None
        assert launch_agent.program_version([str(tmp_path / "missing")]) is None


class TestInstallPin:
    def test_the_engine_pins_itself_when_it_installs(self, tmp_path, monkeypatch, backup_root):
        exe = _freeze(monkeypatch, tmp_path / "Applications" / "Altero.app")
        with patch.object(launch_agent, "_wait_until_unloaded", return_value=True), \
             patch.object(launch_agent.subprocess, "run", side_effect=_launchctl_ok):
            result = launch_agent.install(
                launch_agent.AUTO_LABEL, tmp_path, uid=UID, args=launch_agent.BACKEND_ARGS
            )
        assert result["program"][0] == str(exe)
        assert load_service_settings(backup_root).program == str(exe)

    def test_a_relocated_engine_writes_nothing(self, tmp_path, monkeypatch, backup_root):
        _freeze(monkeypatch, tmp_path / "AppTranslocation" / "Q" / "Altero.app")
        with patch.object(launch_agent.subprocess, "run", side_effect=_launchctl_ok) as run, \
             pytest.raises(ClaudeSwitchError):
            launch_agent.install(launch_agent.AUTO_LABEL, tmp_path, uid=UID)
        run.assert_not_called()
        assert not launch_agent.plist_path(launch_agent.AUTO_LABEL, tmp_path).exists()
        assert load_service_settings(backup_root).program is None

    def test_a_client_installs_the_pinned_program_and_its_version(self, tmp_path, backup_root):
        pinned = _executable(tmp_path / "Altero.app" / ENGINE_REL)
        set_setting(backup_root, "service.program", str(pinned))
        with patch.object(launch_agent, "resolve_program", return_value=["/uv/altero"]), \
             patch.object(launch_agent, "program_version", return_value="9.9.9"), \
             patch.object(launch_agent, "_wait_until_unloaded", return_value=True), \
             patch.object(launch_agent.subprocess, "run", side_effect=_launchctl_ok):
            launch_agent.install(launch_agent.AUTO_LABEL, tmp_path, uid=UID,
                                 args=launch_agent.BACKEND_ARGS)
        plist = plistlib.loads(launch_agent.plist_path(launch_agent.AUTO_LABEL, tmp_path).read_bytes())
        assert plist["ProgramArguments"] == [str(pinned), *launch_agent.BACKEND_ARGS]
        assert plist["EnvironmentVariables"]["ALTERO_VERSION"] == "9.9.9"
        # A client never rewrites the pin.
        assert load_service_settings(backup_root).program == str(pinned)

    def test_a_client_leaves_the_apps_running_backend_alone(self, tmp_path, backup_root):
        # The fight this replaces: a uv altero of another version saw "different
        # argv, different version" and reinstalled itself on every open.
        pinned = _executable(tmp_path / "Altero.app" / ENGINE_REL)
        set_setting(backup_root, "service.program", str(pinned))
        plist = launch_agent.plist_path(launch_agent.AUTO_LABEL, tmp_path)
        plist.parent.mkdir(parents=True)
        plist.write_bytes(plistlib.dumps({
            "Label": launch_agent.AUTO_LABEL,
            "ProgramArguments": [str(pinned), *launch_agent.BACKEND_ARGS],
            "EnvironmentVariables": {"ALTERO_VERSION": "9.9.9"},
        }))
        running = subprocess.CompletedProcess([], 0, stdout="\tstate = running\n\tpid = 7\n", stderr="")
        with patch.object(launch_agent, "resolve_program", return_value=["/uv/altero"]), \
             patch.object(launch_agent, "program_version", return_value="9.9.9"), \
             patch.object(launch_agent.subprocess, "run", return_value=running):
            assert not launch_agent.needs_install(
                launch_agent.AUTO_LABEL, launch_agent.BACKEND_ARGS, tmp_path, UID
            )
        # ...but an app upgraded in place (new version, same path) is replaced.
        with patch.object(launch_agent, "resolve_program", return_value=["/uv/altero"]), \
             patch.object(launch_agent, "program_version", return_value="10.0.0"), \
             patch.object(launch_agent.subprocess, "run", return_value=running):
            assert launch_agent.needs_install(
                launch_agent.AUTO_LABEL, launch_agent.BACKEND_ARGS, tmp_path, UID
            )

    def test_an_unknown_pinned_version_does_not_force_reinstalls(self, tmp_path, backup_root):
        pinned = _executable(tmp_path / "Altero.app" / ENGINE_REL)
        set_setting(backup_root, "service.program", str(pinned))
        plist = launch_agent.plist_path(launch_agent.AUTO_LABEL, tmp_path)
        plist.parent.mkdir(parents=True)
        plist.write_bytes(plistlib.dumps({
            "Label": launch_agent.AUTO_LABEL,
            "ProgramArguments": [str(pinned), *launch_agent.BACKEND_ARGS],
        }))
        running = subprocess.CompletedProcess([], 0, stdout="\tpid = 7\n", stderr="")
        with patch.object(launch_agent, "resolve_program", return_value=["/uv/altero"]), \
             patch.object(launch_agent, "program_version", return_value=None), \
             patch.object(launch_agent.subprocess, "run", return_value=running):
            assert not launch_agent.needs_install(
                launch_agent.AUTO_LABEL, launch_agent.BACKEND_ARGS, tmp_path, UID
            )


class TestWidgetHost:
    def test_the_engines_own_app_is_asked_first(self, tmp_path, monkeypatch):
        app = tmp_path / "Elsewhere" / "Altero.app"
        _freeze(monkeypatch, app)
        candidates = launch_agent.widget_host_candidates(tmp_path)
        assert candidates[0] == app / "Contents" / "MacOS" / "Altero"
        assert candidates[1] == tmp_path / "Applications" / "Altero.app" / "Contents" / "MacOS" / "Altero"


class TestNotificationIdentity:
    def test_does_not_write_into_a_signed_bundle(self, tmp_path, monkeypatch):
        exe = _freeze(monkeypatch, tmp_path / "Altero.app")
        assert menubar.ensure_notification_identity(exe, platform="darwin") is None
        assert not (exe.parent / "Info.plist").exists()


def _release(tag: str) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps({"tag_name": tag}).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestAppUpdates:
    def test_the_app_is_its_own_install_method(self, tmp_path, monkeypatch):
        _freeze(monkeypatch, tmp_path / "Altero.app")
        assert update_check._detect_install_method() == "app"

    def test_the_app_checks_github_releases(self, tmp_path, monkeypatch):
        _freeze(monkeypatch, tmp_path / "Altero.app")
        monkeypatch.setattr(update_check, "PUBLISHED_ON_PYPI", False)
        monkeypatch.setattr(update_check, "APP_CACHE_PATH", tmp_path / "app-cache.json")
        with patch.object(update_check.urllib.request, "urlopen", return_value=_release("v0.4.0")) as urlopen:
            message = update_check.check_for_update("0.3.0")
        assert urlopen.call_args.args[0].full_url == update_check.RELEASES_API_URL
        assert "0.4.0" in message and bundle.RELEASES_URL in message
        assert "altero upgrade" not in message

    def test_upgrade_explains_instead_of_running_uv(self, tmp_path, monkeypatch, capsys):
        _freeze(monkeypatch, tmp_path / "Altero.app")
        with patch.object(update_check.subprocess, "run") as run:
            assert update_check.run_self_upgrade() == 1
        run.assert_not_called()
        assert bundle.RELEASES_URL in capsys.readouterr().out


class TestInstallCliTool:
    def test_links_the_engine_into_local_bin(self, tmp_path, monkeypatch):
        exe = _freeze(monkeypatch, tmp_path / "Applications" / "Altero.app")
        message = bundle.install_cli_tool(home=tmp_path)
        link = tmp_path / ".local" / "bin" / "altero"
        assert os.readlink(link) == str(exe)
        assert str(link) in message and "/usr/local/bin" in message
        assert "already installed" in bundle.install_cli_tool(home=tmp_path)

    def test_never_replaces_someone_elses_altero(self, tmp_path, monkeypatch):
        _freeze(monkeypatch, tmp_path / "Applications" / "Altero.app")
        uv_tool = _executable(tmp_path / "uv" / "tools" / "altero" / "bin" / "altero")
        link = tmp_path / ".local" / "bin" / "altero"
        link.parent.mkdir(parents=True)
        link.symlink_to(uv_tool)
        with pytest.raises(ClaudeSwitchError, match="left alone"):
            bundle.install_cli_tool(home=tmp_path)
        assert os.readlink(link) == str(uv_tool)

    def test_replaces_a_dangling_link(self, tmp_path, monkeypatch):
        exe = _freeze(monkeypatch, tmp_path / "Applications" / "Altero.app")
        link = tmp_path / ".local" / "bin" / "altero"
        link.parent.mkdir(parents=True)
        link.symlink_to(tmp_path / "moved-away" / "altero")
        bundle.install_cli_tool(home=tmp_path)
        assert os.readlink(link) == str(exe)

    def test_refuses_from_the_disk_image(self, tmp_path, monkeypatch):
        _freeze(monkeypatch, tmp_path / "AppTranslocation" / "Z" / "Altero.app")
        with pytest.raises(ClaudeSwitchError, match="Applications"):
            bundle.install_cli_tool(home=tmp_path)
        assert not (tmp_path / ".local" / "bin" / "altero").exists()

    def test_only_from_the_app(self, tmp_path):
        with pytest.raises(ClaudeSwitchError, match="only be installed from Altero.app"):
            bundle.install_cli_tool(home=tmp_path)
