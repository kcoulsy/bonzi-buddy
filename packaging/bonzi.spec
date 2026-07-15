# PyInstaller spec — one self-contained executable with all assets baked in.
# Build:  pyinstaller packaging/bonzi.spec
import os
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

# PyInstaller's Qt hook includes every plugin installed by the system package.
# Bonzi needs the native desktop platform plus PNG/ICO support for its assets.
qt_plugin_prefixes = (
    "PySide6/Qt/plugins/egldeviceintegrations/",
    "PySide6/Qt/plugins/generic/",
    "PySide6/Qt/plugins/networkinformation/",
    "PySide6/Qt/plugins/platforminputcontexts/",
    "PySide6/Qt/plugins/platformthemes/",
    "PySide6/Qt/plugins/styles/",
    "PySide6/Qt/plugins/tls/",
    "PySide6/Qt/plugins/wayland-",
    "PySide6/Qt/plugins/xcbglintegrations/",
)
qt_unused_library_prefixes = (
    "kf6", "layershell", "qt6pdf", "qt6qml", "qt6quick", "qt6virtualkeyboard",
    "qt6wayland",
)
qt_unused_libraries = {
    # These are brought in only by the excluded image-format plugins.
    "libaom.so.3", "libavif.so.16", "libdav1d.so.7", "libglycin-2.so.0",
    "libiex-3_4.so.33", "libilmthread-3_4.so.33", "libjbig.so.2.1",
    "libjxl.so.0.12", "libjxl_cms.so.0.12", "libjxl_threads.so.0.12",
    "libopenexr-3_4.so.33", "libopenexrcore-3_4.so.33", "libopenjph.so.0.30",
    "libraw.so.25", "librav1e.so.0.8", "libsvtav1enc.so.4", "libtiff.so.6",
    # NumPy's linear algebra backend is unused by the ACS parser.
    "libblas.so.3", "libcblas.so.3", "libgfortran.so.5", "liblapack.so.3",
}
qt_platform_plugin = {
    "linux": "libqxcb.so",
    "win32": "qwindows.dll",
    "darwin": "libqcocoa.dylib",
}.get(sys.platform)


def qt_name(path):
    return Path(path).stem.lower().removeprefix("lib")


a.binaries = [
    entry for entry in a.binaries
    if not entry[0].startswith(qt_plugin_prefixes)
    and not (
        entry[0].startswith("PySide6/Qt/plugins/imageformats/")
        and qt_name(entry[0]) not in {"qgif", "qico", "qjpeg", "qpng"}
    )
    and not (
        entry[0].startswith("PySide6/Qt/plugins/platforms/")
        and Path(entry[0]).name != qt_platform_plugin
    )
    and not qt_name(entry[0]).startswith(qt_unused_library_prefixes)
    and Path(entry[0]).name.lower() not in qt_unused_libraries
]

if sys.platform == "win32":
    # These API-set DLLs are Windows loader forwarders, not application
    # dependencies. Windows 10/11 supplies their contracts; app-local copies
    # from the build Python can shadow the OS mapping during bootstrapping.
    a.binaries = [
        entry for entry in a.binaries
        if not Path(entry[0]).name.lower().startswith("api-ms-win-")
    ]

pyz = PYZ(a.pure)

onefile = os.environ.get("BONZI_BUILD_MODE", "onefile") == "onefile"

if onefile:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [], name="bonzi",
        debug=False,
        # GNU strip modifies Python and runtime PE DLLs. Do not process them.
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        icon=icon,
    )
else:
    exe = EXE(
        pyz, a.scripts, [], exclude_binaries=True, name="bonzi",
        debug=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        icon=icon,
    )
    COLLECT(exe, a.binaries, a.datas, name="bonzi-onedir")

# On macOS, also wrap the binary in a double-clickable .app bundle.
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Bonzi.app",
        icon=None,
        bundle_identifier="com.tmafe.bonzi.linux",
        info_plist={"LSUIElement": True},  # tray/pet app: no dock bouncing
    )
