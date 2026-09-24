# Releasing Altero.app

Altero.app is one signed, notarized app: the widget host and widget (Swift,
from `widget/`) with the Python engine (CLI, TUI, menu bar, backend) nested
at `Contents/Helpers/AlteroEngine.app`. It ships as a DMG on GitHub Releases.
`packaging/build-app` builds all of it; this file is what it needs and the
steps around it.

## Prerequisites (once per machine)

1. **An Apple silicon Mac** with Xcode, and `brew install uv xcodegen`. The
   engine is arm64 only and is frozen on the machine that builds it.

2. **The Team ID** in `widget/Signing.xcconfig` (gitignored):

   ```bash
   cp widget/Signing.xcconfig.example widget/Signing.xcconfig
   # then set: DEVELOPMENT_TEAM = KQ6GZN2P9N
   ```

   The script uses it to pick the Developer ID identity of that team.
   `ALTERO_TEAM_ID` overrides it (CI).

3. **A Developer ID Application certificate** in the login keychain. Only the
   Account Holder can create one: Xcode > Settings > Accounts > Manage
   Certificates > + > Developer ID Application, or
   <https://developer.apple.com/account/resources/certificates> with a CSR from
   Keychain Access. Check it:

   ```bash
   security find-identity -v -p codesigning | grep "Developer ID Application"
   ```

   A certificate that exists but is not listed there has a broken chain, not a
   broken account: `security find-identity -p codesigning` (no `-v`) shows it
   as invalid. Import the intermediate it was issued by, usually
   <https://www.apple.com/certificateauthority/DeveloperIDG2CA.cer>. Not a
   "Developer ID Installer" certificate: that one is for `.pkg`.

4. **A notarytool keychain profile** named `altero-notary`:

   ```bash
   xcrun notarytool store-credentials altero-notary \
       --apple-id <your Apple ID> --team-id KQ6GZN2P9N \
       --password <app-specific password from https://account.apple.com>
   ```

   For CI, an App Store Connect API key works instead of a password
   (`--key AuthKey_XXXX.p8 --key-id <id> --issuer <issuer>`). Another profile
   name goes in `ALTERO_NOTARY_PROFILE`.

`packaging/build-app --release` checks all of this before it builds and lists
everything that is missing at once.

## Release

1. **Version.** Set `version` in `pyproject.toml`, run `uv lock`, and move the
   `[Unreleased]` notes in `CHANGELOG.md` under the version. Merge to `main`.
   The app's `CFBundleShortVersionString` is the version's first three numbers
   (`0.1.0.dev0` gives `0.1.0`); the DMG name carries the full version.

2. **Build, sign, notarize** from a clean checkout of `main`:

   ```bash
   packaging/build-app --release
   ```

   In about a minute plus Apple's notarization queue, it:

   - freezes the engine with PyInstaller from a uv-managed CPython 3.13 and
     the locked, hash-checked dependencies;
   - archives the Xcode project (arm64) and nests the engine in it;
   - signs every Mach-O inside-out with the Developer ID identity, hardened
     runtime, a secure timestamp, and the entitlements files in the repo;
   - verifies: `codesign --verify --deep --strict`, no `get-task-allow`, the
     signed engine's `--version`;
   - notarizes the app, staples it, builds the DMG from the stapled app, signs,
     notarizes and staples the DMG, and checks both with `spctl`.

   It ends with a summary, and the DMG is at `build/app/Altero-<version>.dmg`.
   A rejected submission prints `notarytool log` for it.

3. **Try it** on this Mac before publishing:

   ```bash
   packaging/install-app                       # build/app/Altero.app -> /Applications
   spctl -a -vv /Applications/Altero.app       # accepted, source=Notarized Developer ID
   xcrun stapler validate build/app/Altero-<version>.dmg
   ```

   `install-app` stops the services running the app it replaces, swaps the
   app, and starts them again through the new engine (see "Upgrades"). Then
   open Altero, check the menu bar, **Install Command Line Tool…**, the widget,
   and `altero service status` (the program is the app's engine).

4. **Publish.** The tag is `v` plus the version: the app's update check reads
   the latest release's tag.

   ```bash
   git tag v0.1.0 && git push origin v0.1.0
   gh release create v0.1.0 build/app/Altero-0.1.0.dmg \
       --title "Altero 0.1.0" --notes-file <notes>
   ```

   Mark test builds `--prerelease`: GitHub's "latest" skips them, so installed
   apps are not told to update to one.

## Upgrades

The engine loads Python modules lazily from files inside the app, so an app
replaced while its backend or menu bar runs can crash them on a later import.
`packaging/install-app` avoids that by stopping those services first. A DMG
user does the same by quitting Altero from the menu bar before replacing the
app; opening the new app reinstalls the services on the new version. The
Homebrew cask, when it exists, will stop and restart them in its
`preflight`/`postflight` and remove the LaunchAgents on uninstall.

## Local and CI builds

Without `--release` the script signs with the best identity it finds and says
which: Developer ID, else Apple Development (runs on this Mac, rejected by
Gatekeeper elsewhere), else ad-hoc (no hardened runtime, since library
validation needs a Team ID). Gatekeeper's verdict is reported, not fatal.
Nothing prompts; everything is set through the environment:

| Variable | Default |
|---|---|
| `ALTERO_SIGN_IDENTITY` | auto-detect; a name, a SHA-1, or `-` for ad-hoc |
| `ALTERO_TEAM_ID` | `DEVELOPMENT_TEAM` in `widget/Signing.xcconfig` |
| `ALTERO_NOTARY_PROFILE` | `altero-notary` |
| `ALTERO_BUILD_NUMBER` | a timestamp (`CFBundleVersion`) |

Every run starts `build/app/` over. The script unregisters its build products
from LaunchServices afterwards: `xcodebuild` registers what it builds, and a
second registered copy of the widget extension can take the widget away from
the installed app (see `widget/README.md`).

## Not yet verified

- The first notarization. The widget's `temporary-exception` entitlements are
  expected to pass (they are not profile-gated, and notarization is an
  automated scan, not App Review), but only a submission proves it.
- `install-app` against running services.
