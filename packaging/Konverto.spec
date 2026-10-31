# PyInstaller-Spec fuer Konverto. Wird von packaging/build.py aufgerufen.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH).parent

datas = [(str(ROOT / "THIRD_PARTY_NOTICES.txt"), ".")]
binaries = []
hiddenimports = ["markdown.extensions.tables", "markdown.extensions.fenced_code", "markdown.extensions.sane_lists"]
for pkg in ("imageio_ffmpeg", "pillow_heif"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
datas += collect_data_files("docx")

a = Analysis(
    [str(ROOT / "Konverto.pyw")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "unittest", "pydoc_data", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtNetwork",
              "PySide6.QtPdf", "PySide6.QtOpenGL", "PySide6.QtWebEngineCore"],
)

# Qt-Teile, die Konverto nicht braucht (Software-OpenGL, QML, PDF-Plugin, Uebersetzungen)
DROP = ("opengl32sw.dll", "qt6quick", "qt6qml", "qt6pdf", "qpdf.dll", "qt6virtualkeyboard", "qt6network",
        "qt6opengl", "d3dcompiler")
a.binaries = [b for b in a.binaries if not any(x in b[0].lower() for x in DROP)]
a.datas = [d for d in a.datas if "pyside6\\translations" not in d[0].lower().replace("/", "\\")]
# entpackte docx-Vorlage (auch vom PyInstaller-Hook gesammelt) enthaelt "[Content_Types].xml" –
# in MSIX ein reservierter Name und zur Laufzeit unnoetig
a.datas = [d for d in a.datas if "default-docx-template" not in d[0]]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Konverto",
    console=False,
    icon=str(ROOT / "assets" / "icon.ico"),
    version=str(Path(workpath).parent / "version_info.txt"),  # workpath = <--workpath>/Konverto
)
coll = COLLECT(exe, a.binaries, a.datas, name="Konverto")
