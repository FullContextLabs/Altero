# Changelog

All notable changes to Altero are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Switching no longer backs up an OAuth-less live store (API key or
  mcpOAuth-only leftover) over a slot's OAuth backup, and a newer foreign
  login is saved into its owning slot instead of only being stashed (upstream
  [#384](https://github.com/realiti4/claude-swap/pull/384) by @NorthIsUp).
- Switching no longer reverts a slot's newer re-login to a stale live
  credential of the same account, including via the foreign-owner write path
  (upstream [#334](https://github.com/realiti4/claude-swap/pull/334) by
  @ardabayhan).
- On macOS under a custom `CLAUDE_CONFIG_DIR`, switching no longer overwrites
  the default profile's Keychain login; it seeds the profile's own credentials
  file and clears the item the read resolves (upstream
  [#357](https://github.com/realiti4/claude-swap/pull/357) by
  @BarganConstantin).

## [0.1.1] - 2026-09-25

### Fixed

- Login Items and the background-items notification now name Altero instead
  of the signing developer.

## [0.1.0] - 2026-09-24

### Added

- Altero for Claude Code: CLI and TUI (macOS, Windows, Linux), macOS menu bar,
  background auto-switch service and desktop widget.
- Data directory `~/.altero` (macOS, Windows) and
  `${XDG_DATA_HOME:-~/.local/share}/altero` (Linux, WSL).
- LaunchAgent labels and bundle ids under `com.fullcontextlabs.altero.*`.
- Altero is now published on PyPI; the PyPI update check is on.
- Altero.app awareness: inside the app, the services run the bundled engine
  and pin it (`service.program`), so a pip/uv `altero` becomes a client of the
  app's services instead of repointing them. The app refuses to install
  services from the disk image, App Translocation or `~/Downloads`, offers
  "Install Command Line Tool…" in the menu bar, and checks GitHub Releases
  for updates.
- Altero.app: `packaging/build-app` builds the signed app with the engine
  inside and a DMG, and with `--release` notarizes and staples both.
  `packaging/install-app` upgrades an installed app without replacing it
  under running services.
