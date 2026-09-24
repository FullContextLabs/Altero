# PyInstaller spec for AlteroEngine.app, the Python half of Altero.app.
#
# Run by packaging/build-app, which sets the ALTERO_* variables below. The
# result is a onedir .app bundle (not onefile: onefile unpacks to a temp dir
# on every launch, which is slow and cannot be signed as shipped) that the
# script nests at Altero.app/Contents/Helpers/AlteroEngine.app.
#
# It is an .app of its own, with its own bundle id, for two reasons:
# rumps needs NSBundle.mainBundle to have an identifier for notifications,
# and a bundle id shared with the host would have LaunchServices hand the
# host's altero:// URLs to the running menu bar instead.
#
# Signing is left to build-app (codesign_identity=None): it signs every
# Mach-O inside-out with the hardened runtime after the bundle is nested.
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

short_version = os.environ["ALTERO_SHORT_VERSION"]
build_number = os.environ["ALTERO_BUILD_NUMBER"]
icon = os.environ.get("ALTERO_ENGINE_ICON") or None

# altero's data files (the TUI's altero.tcss) are not Python modules, and
# nothing imports them, so only collect_data_files brings them along. Its
# metadata is what importlib.metadata.version("altero") reads for
# __version__. textual imports its widgets lazily by name, which static
# analysis cannot follow; same for altero's function-level imports.
datas = collect_data_files("altero") + collect_data_files("textual")
datas += copy_metadata("altero") + copy_metadata("textual")
hiddenimports = collect_submodules("altero") + collect_submodules("textual")

a = Analysis(
    [os.path.join(SPECPATH, "engine_entry.py")],
    datas=datas,
    hiddenimports=hiddenimports,
    # Nothing here is used at runtime; tkinter alone is ~10 MB.
    excludes=["tkinter", "_tkinter", "test", "PyObjCTest", "pip", "setuptools", "pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="altero",
    debug=False,
    strip=False,
    # UPX-packed binaries do not survive code signing.
    upx=False,
    # A BUNDLE build; stdout/stderr still reach a terminal that runs it.
    console=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="AlteroEngine")
app = BUNDLE(
    coll,
    name="AlteroEngine.app",
    icon=icon,
    bundle_identifier="com.fullcontextlabs.altero.engine",
    version=short_version,
    info_plist={
        # What notifications and Login Items show for the menu bar.
        "CFBundleName": "Altero",
        "CFBundleDisplayName": "Altero",
        "CFBundleVersion": build_number,
        "LSMinimumSystemVersion": "14.0",
        # A menu bar app and a CLI: never a Dock icon.
        "LSUIElement": True,
        "NSHumanReadableCopyright": "Copyright © 2026 Full Context Labs. MIT License.",
    },
)
