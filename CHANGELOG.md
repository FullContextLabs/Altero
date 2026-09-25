# Changelog

All notable changes to Altero are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
