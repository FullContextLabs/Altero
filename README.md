# Altero

**Altero for Claude Code.** Keep several Claude Code accounts on one machine and switch between them without logging out. Altero watches every account's usage and switches for you before the active one hits its limit.

Not affiliated with Anthropic.

- Switch accounts from the CLI, a terminal dashboard (TUI), the macOS menu bar or a macOS widget.
- Auto-switch before the 5-hour or 7-day window runs out, onto the account with the most quota left.
- Run two accounts side by side, one per terminal (session mode).
- Works with the Claude Code CLI and the VS Code extension.

## Platform support

| | macOS | Windows | Linux / WSL |
|---|:-:|:-:|:-:|
| CLI (`altero list`, `switch`, `add`, `run`, ...) | Yes | Yes | Yes |
| TUI dashboard (`altero`, `altero watch`) | Yes | Yes | Yes |
| Auto-switch engine | Background service | Foreground only | Foreground only |
| Menu bar app | Yes | No | No |
| Desktop widget | Yes (built from source) | No | No |
| Signed, notarized app | Planned | No | No |

On macOS the auto-switch engine runs as a per-user LaunchAgent that the TUI and menu bar start on their own and that stops once no surface or widget is open. On Windows and Linux there is no system service. The engine runs only while `altero auto` or the TUI is open in a terminal. `altero menubar` and `altero service` refuse to run off macOS. For unattended use there, run `altero auto --once` from cron or a systemd timer.

## Install

Altero is not on PyPI yet. Install it from GitHub with [uv](https://docs.astral.sh/uv/) (Python 3.12+):

```bash
uv tool install 'git+https://github.com/FullContextLabs/Altero'
# macOS, with the menu bar:
uv tool install 'altero[menubar] @ git+https://github.com/FullContextLabs/Altero'
```

`pipx install` accepts the same specs. `altero upgrade` upgrades a uv or pipx install.

From source:

```bash
git clone https://github.com/FullContextLabs/Altero.git
cd Altero
uv sync --all-extras
uv run altero help
```

The desktop widget is built from `widget/` with Xcode. See [widget/README.md](widget/README.md).

## Quick start

```bash
# Log in to Claude Code with your first account, then:
altero add
# Log in with the next account (no /logout first; it can revoke the stored token), then:
altero add

altero list              # every account's 5h / 7d usage and reset times
altero switch            # rotate to the next account
altero switch 2          # or a specific one: number, email or alias
altero                   # the TUI dashboard
altero auto              # auto-switch in the foreground
altero menubar           # macOS: menu bar app, starts at login
altero run 2             # run Claude Code as account 2 in this terminal only
```

Usually no restart is needed after a switch. On Linux and Windows, Claude Code re-reads the credentials file on its next message. On macOS the Keychain value is cached for about 30 seconds. Restart Claude Code, or reopen the VS Code tab, to apply a switch immediately.

`altero help` lists every command. `altero config` shows and changes settings.

## How auto-switch works

- The engine polls usage for your accounts. When the active account's 5-hour or 7-day window reaches the threshold (default 90%), it switches to the account with the most quota left. `--model Fable` also counts that model's weekly limit.
- A cooldown (default 5 minutes) and a hysteresis margin stop it flip-flopping near the threshold. A manual switch from any surface starts the same cooldown.
- A switch holds Claude Code's own credential locks, so it never collides with a token refresh, and is safe while Claude Code is working.
- Polling is adaptive and paced per account. Opening more dashboards does not fetch more often.
- It fails safe. On a failed usage check it keeps the last known numbers. An account whose refresh token has died is quarantined until you re-add it.
- `altero disable N` holds an account out of rotation. `--strategy consume-first` spends the account whose weekly window resets soonest first.
- It is on by default. Turn it off with `altero config set autoswitch.enabled false`, and the engine keeps polling and reporting without switching.

```bash
altero auto --threshold 80     # switch earlier
altero auto --once --json      # one check, for cron/systemd; exit code 0 switched, 2 nothing to do
altero service status          # macOS: is the background engine running
altero service logs -f         # macOS: follow its events
```

## Data

| Platform | Data directory | Account credentials |
|---|---|---|
| macOS | `~/.altero/` | macOS Keychain (service `altero`) |
| Windows | `~/.altero/` | Files under `credentials/` in the data directory |
| Linux / WSL | `${XDG_DATA_HOME:-~/.local/share}/altero/` | Files under `credentials/` in the data directory |

`altero purge` removes Altero's data and stored credentials. It does not touch your Claude Code login.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): the backend, the surfaces and the snapshot contract
- [TESTING.md](TESTING.md): the test runbook
- [widget/README.md](widget/README.md): building and installing the widget
- [SECURITY.md](SECURITY.md): reporting a vulnerability
- [CHANGELOG.md](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE).

Altero is not affiliated with, endorsed by or sponsored by Anthropic. Claude and Claude Code are trademarks of Anthropic.
