# PyInstaller spec — one self-contained executable with all assets baked in.
# Build:  pyinstaller packaging/bonzi.spec
import sys
from pathlib import Path

root = Path(SPECPATH).resolve().parent  # repo root (SPECPATH == packaging/)

# Bundle the whole assets/ tree (Bonzi.acs, images/, icons) inside the exe.
datas = [(str(root / "assets"), "assets")]

icon = None
if sys.platform == "win32":
    icon = str(root / "assets" / "bonzi.ico")

a = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["bonzi", "bonzi.acs", "bonzi.runtime"],
    hookspath=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="bonzi",
    debug=False,
    strip=False,
    upx=False,
    console=False,           # GUI app: no terminal window on Windows
    disable_windowed_traceback=False,
    icon=icon,
)

# On macOS, also wrap the binary in a double-clickable .app bundle.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Bonzi.app",
        icon=None,
        bundle_identifier="com.tmafe.bonzi.linux",
        info_plist={"LSUIElement": True},  # tray/pet app: no dock bouncing
    )
