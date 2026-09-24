# Changelog

All notable changes to Altero are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

First release, 0.1.0.

### Added

- Altero for Claude Code: CLI and TUI (macOS, Windows, Linux), macOS menu bar,
  background auto-switch service and desktop widget.
- Data directory `~/.altero` (macOS, Windows) and
  `${XDG_DATA_HOME:-~/.local/share}/altero` (Linux, WSL).
- LaunchAgent labels and bundle ids under `com.fullcontextlabs.altero.*`.
- The PyPI update check is disabled until Altero is published.
- Altero.app awareness: inside the app, the services run the bundled engine
  and pin it (`service.program`), so a pip/uv `altero` becomes a client of the
  app's services instead of repointing them. The app refuses to install
  services from the disk image, App Translocation or `~/Downloads`, offers
  "Install Command Line Tool…" in the menu bar, and checks GitHub Releases
  for updates.
