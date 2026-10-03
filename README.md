# Altero

[![CI](https://github.com/FullContextLabs/Altero/actions/workflows/ci.yml/badge.svg)](https://github.com/FullContextLabs/Altero/actions/workflows/ci.yml)

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
| Desktop widget | Yes | No | No |
| Signed, notarized app (Altero.app) | Yes | No | No |

On macOS the auto-switch engine runs as a per-user LaunchAgent that the TUI and menu bar start on their own and that stops once no surface or widget is open. On Windows and Linux there is no system service. The engine runs only while `altero auto` or the TUI is open in a terminal. `altero menubar` and `altero service` refuse to run off macOS. For unattended use there, run `altero auto --once` from cron or a systemd timer.

## Install

### macOS: Altero.app

One app with everything: the CLI, the TUI, the menu bar, the background engine and the widget. Apple silicon, macOS 14 or later.

With [Homebrew](https://brew.sh), `brew install fullcontextlabs/tap/altero` installs the app and puts `altero` on your PATH. Upgrade with `brew upgrade --cask altero`. Otherwise:

1. Download `Altero-<version>.dmg` from [Releases](https://github.com/FullContextLabs/Altero/releases/latest).
2. Open it and drag **Altero** into **Applications**.
3. Open Altero from Applications. The menu bar icon appears, and macOS notes that Altero added background items (the menu bar and the auto-switch engine, which start at login).
4. For the `altero` command in a terminal, accept the offer Altero makes on first launch, or choose **Install Command Line Tool…** from the menu bar later. It links `/usr/local/bin/altero` to the app, and macOS may ask for your administrator password to do so. If you cancel that prompt, it links `~/.local/bin/altero` instead and adds `~/.local/bin` to your PATH in `~/.zprofile`; open a new terminal afterwards. If another `altero` (a uv or pip install) is already there, it is left alone. To link it by hand:

   ```bash
   sudo ln -sf /Applications/Altero.app/Contents/Helpers/AlteroEngine.app/Contents/MacOS/altero /usr/local/bin/altero
   ```
5. For the widget: right-click the desktop, **Edit Widgets**, and look for **Altero**.

Altero refuses to start from the disk image or the Downloads folder, because its login services would point at a path that is gone at the next login. Move it to Applications first.

To upgrade, quit Altero from its menu bar, replace the app in Applications with the new one, and open it again.

If you also have a uv or pip install, the app's engine owns the background services and the other `altero` uses them instead of replacing them. `altero config unset service.program` hands them back until the app is opened again.

### CLI with uv or pipx (macOS, Windows, Linux)

Install with [uv](https://docs.astral.sh/uv/) (Python 3.12+):

```bash
uv tool install altero
# macOS, with the menu bar:
uv tool install 'altero[menubar]'
```

`pipx install altero` works the same way. `altero upgrade` upgrades a uv or pipx install.

From GitHub, for an unreleased commit:

```bash
uv tool install 'git+https://github.com/FullContextLabs/Altero'
```

From source:

```bash
git clone https://github.com/FullContextLabs/Altero.git
cd Altero
uv sync --all-extras
uv run altero help
```

To build the widget from source, see [widget/README.md](widget/README.md). To build Altero.app, see [RELEASING.md](RELEASING.md).

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

## Uninstall

Removing the app or the CLI keeps your accounts. To delete them too, see [Remove your data](#remove-your-data), and do that first: it needs the `altero` command.

### Homebrew

```bash
brew uninstall --cask altero
```

This stops the background services, quits the app and removes Altero.app, the `altero` link and the two LaunchAgents. To also remove logs and the widget container, use `brew uninstall --zap --cask altero`.

If you used **Install Command Line Tool…** in the app, remove its link too (it is owned by root):

```bash
sudo rm /usr/local/bin/altero
```

If it fell back to `~/.local/bin`, run `rm ~/.local/bin/altero` and delete the `# added by Altero` block from `~/.zprofile`.

The widget can keep running after the app is gone. Remove it from the desktop or Notification Center, or log out.

### macOS: Altero.app (DMG)

1. Quit Altero from its menu bar, then stop the background services:

   ```bash
   for label in menubar auto; do
     launchctl bootout gui/$(id -u)/com.fullcontextlabs.altero.$label
   done
   ```

   The plists are what start them at login. Remove them, or they come back at the next login:

   ```bash
   rm -f ~/Library/LaunchAgents/com.fullcontextlabs.altero.{menubar,auto}.plist
   ```
2. Delete **Altero** from Applications.
3. Remove the command line links, if you installed them:

   ```bash
   sudo rm -f /usr/local/bin/altero
   rm -f ~/.local/bin/altero
   ```

   If Altero added `~/.local/bin` to your PATH, delete the `# added by Altero` block from `~/.zprofile`.
4. Optional leftovers:

   ```bash
   rm -f ~/Library/Logs/com.fullcontextlabs.altero.*
   rm -rf ~/Library/Containers/com.fullcontextlabs.altero.widget
   ```

The widget can keep running after the app is gone. Remove it from the desktop or Notification Center, or log out.

### uv or pipx

On macOS, stop the background services first. The LaunchAgents point at the `altero` command and would otherwise keep trying to start it.

```bash
for label in menubar auto; do
  launchctl bootout gui/$(id -u)/com.fullcontextlabs.altero.$label
done
rm -f ~/Library/LaunchAgents/com.fullcontextlabs.altero.{menubar,auto}.plist
```

Then remove the package:

```bash
uv tool uninstall altero
# or
pipx uninstall altero
```

### Remove your data

`~/.altero` holds your accounts and credentials. Deleting it is permanent and cannot be undone. On macOS the credentials also live in the Keychain, so run this before uninstalling instead of deleting the folder:

```bash
altero purge
```

It removes the data directory and the stored credentials, and does not touch your Claude Code login. See [Data](#data) for where each platform keeps them.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): the backend, the surfaces and the snapshot contract
- [TESTING.md](TESTING.md): the test runbook
- [widget/README.md](widget/README.md): building and installing the widget
- [RELEASING.md](RELEASING.md): building, signing and notarizing Altero.app
- [SECURITY.md](SECURITY.md): reporting a vulnerability
- [CHANGELOG.md](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE).

Altero is not affiliated with, endorsed by or sponsored by Anthropic. Claude and Claude Code are trademarks of Anthropic.
