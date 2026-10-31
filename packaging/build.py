"""Baut Konverto.exe und optional das MSIX-Paket fuer den Microsoft Store.

    python packaging/build.py            -> dist/Konverto/Konverto.exe
    python packaging/build.py --msix     -> zusaetzlich dist/Konverto_<version>_x64.msix (Store-Upload)
    python packaging/build.py --msix --sign
                                         -> zusaetzlich signiertes Test-MSIX zum lokalen Installieren
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "packaging"
DIST = ROOT / "dist"
WORK = Path(tempfile.gettempdir()) / "konverto_build"
sys.path.insert(0, str(ROOT))

from konverto import APP_NAME, APP_VERSION  # noqa: E402


def store_version() -> str:
    parts = (APP_VERSION.split(".") + ["0", "0", "0"])[:3]
    return ".".join(parts) + ".0"  # Store verlangt Revision 0


def find_sdk_tool(name: str) -> str:
    base = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits" / "10" / "bin"
    found = sorted(base.glob(f"10.*/x64/{name}"), key=lambda p: [int(x) for x in p.parent.parent.name.split(".")])
    if not found:
        sys.exit(f"{name} nicht gefunden – bitte das Windows SDK installieren (winget install Microsoft.WindowsSDK.10.0.26100)")
    return str(found[-1])


def run(*cmd):
    print(">", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


# ---------------------------------------------------------------- Grafiken

def render_assets(asset_dir: Path, ico_path: Path, bg_color: str):
    from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

    app = QGuiApplication.instance() or QGuiApplication([])
    from konverto.widgets import draw_logo

    def save(img: QImage, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(path), "PNG")

    def tile(w: int, h: int, logo_frac: float, bg: str | None = None) -> QImage:
        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor(bg) if bg else Qt.transparent)
        side = int(min(w, h) * logo_frac)
        p = QPainter(img)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(QRectF((w - side) / 2, (h - side) / 2, side, side).toRect(), draw_logo(side * 2))
        p.end()
        return img

    asset_dir.mkdir(parents=True, exist_ok=True)
    # (Name, Basisbreite, Basishoehe, Logoanteil)
    specs = [
        ("StoreLogo", 50, 50, 1.0),
        ("Square44x44Logo", 44, 44, 1.0),
        ("Square71x71Logo", 71, 71, 0.6),
        ("Square150x150Logo", 150, 150, 0.55),
        ("Square310x310Logo", 310, 310, 0.5),
        ("Wide310x150Logo", 310, 150, 0.55),
        ("SplashScreen", 620, 300, 0.4),
    ]
    for name, w, h, frac in specs:
        for scale in (100, 125, 150, 200, 400):
            img = tile(round(w * scale / 100), round(h * scale / 100), frac)
            save(img, asset_dir / f"{name}.scale-{scale}.png")
    # Taskleiste / Startmenue-Liste: feste Pixelgroessen, mit und ohne "Plate"
    for size in (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256):
        img = tile(size, size, 1.0)
        save(img, asset_dir / f"Square44x44Logo.targetsize-{size}.png")
        save(img, asset_dir / f"Square44x44Logo.targetsize-{size}_altform-unplated.png")
        save(img, asset_dir / f"Square44x44Logo.targetsize-{size}_altform-lightunplated.png")

    # .ico fuer die EXE
    from io import BytesIO

    from PIL import Image

    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    draw_logo(256).save(buf, "PNG")
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    Image.open(BytesIO(bytes(buf.data()))).save(ico_path, sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])


# ---------------------------------------------------------------- EXE

VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}), prodvers=({v}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040704B0', [
      StringStruct('CompanyName', {company!r}),
      StringStruct('FileDescription', 'Konverto – Datei-Konverter'),
      StringStruct('FileVersion', {sv!r}),
      StringStruct('InternalName', 'Konverto'),
      StringStruct('OriginalFilename', 'Konverto.exe'),
      StringStruct('ProductName', 'Konverto'),
      StringStruct('ProductVersion', {sv!r})])]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
"""


def build_exe(cfg: dict):
    WORK.mkdir(parents=True, exist_ok=True)
    sv = store_version()
    (WORK / "version_info.txt").write_text(
        VERSION_INFO.format(v=sv.replace(".", ", "), sv=sv, company=cfg["publisher_display_name"]), encoding="utf-8")
    render_assets(PKG / "msix_assets", ROOT / "assets" / "icon.ico", cfg["background_color"])
    # alter Zwischenordner aus frueheren Builds stiftet nur Verwirrung
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
        "--workpath", WORK, "--distpath", DIST, PKG / "Konverto.spec")
    exe = DIST / "Konverto" / "Konverto.exe"
    size = sum(f.stat().st_size for f in exe.parent.rglob("*") if f.is_file()) / 1024 / 1024
    print(f"\nEXE fertig: {exe}  ({size:.0f} MB)")


# ---------------------------------------------------------------- MSIX

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap rescap">
  <Identity Name="{identity}" Publisher="{publisher}" Version="{version}" ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>{display}</DisplayName>
    <PublisherDisplayName>{publisher_display}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Resources>
    <Resource Language="{language}" />
  </Resources>
  <Applications>
    <Application Id="Konverto" Executable="Konverto\\Konverto.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="{display}" Description="{description}" BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png">
        <uap:DefaultTile Wide310x150Logo="Assets\\Wide310x150Logo.png" Square71x71Logo="Assets\\Square71x71Logo.png"
                         Square310x310Logo="Assets\\Square310x310Logo.png" ShortName="{display}">
          <uap:ShowNameOnTiles>
            <uap:ShowOn Tile="square150x150Logo" />
            <uap:ShowOn Tile="wide310x150Logo" />
            <uap:ShowOn Tile="square310x310Logo" />
          </uap:ShowNameOnTiles>
        </uap:DefaultTile>
        <uap:SplashScreen Image="Assets\\SplashScreen.png" BackgroundColor="{bg}" />
      </uap:VisualElements>
    </Application>
  </Applications>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
"""


def build_msix(cfg: dict, sign: bool) -> Path:
    layout = WORK / "msix_layout"
    shutil.rmtree(layout, ignore_errors=True)
    shutil.copytree(DIST / "Konverto", layout / "Konverto")
    shutil.copytree(PKG / "msix_assets", layout / "Assets")
    version = store_version()
    publisher = cfg["publisher"]
    (layout / "AppxManifest.xml").write_text(MANIFEST.format(
        identity=escape(cfg["identity_name"]), publisher=escape(publisher, {'"': "&quot;"}), version=version,
        display=escape(cfg["display_name"]), publisher_display=escape(cfg["publisher_display_name"]),
        description=escape(cfg["description"], {'"': "&quot;"}), language=cfg["language"], bg=cfg["background_color"],
    ), encoding="utf-8")

    makepri = find_sdk_tool("makepri.exe")
    priconf = WORK / "priconfig.xml"
    run(makepri, "createconfig", "/cf", priconf, "/dq", f"{cfg['language'].lower()}", "/pv", "10.0.0", "/o")
    run(makepri, "new", "/pr", layout, "/cf", priconf, "/mn", layout / "AppxManifest.xml",
        "/of", layout / "resources.pri", "/o")

    out = DIST / f"{APP_NAME}_{version}_x64.msix"
    out.unlink(missing_ok=True)
    run(find_sdk_tool("makeappx.exe"), "pack", "/d", layout, "/p", out, "/o")
    print(f"\nMSIX fertig: {out}  ({out.stat().st_size / 1024 / 1024:.0f} MB)")

    if sign:
        sign_for_testing(out, publisher)
    return out


def sign_for_testing(msix: Path, publisher: str):
    """Signiert mit einem selbst erstellten Zertifikat – nur fuer lokale Tests, der Store signiert selbst."""
    pfx = PKG / "test_cert.pfx"
    cer = PKG / "test_cert.cer"
    if not pfx.exists():
        ps = (
            f"$c = New-SelfSignedCertificate -Type Custom -Subject '{publisher}' -KeyUsage DigitalSignature "
            f"-FriendlyName 'Konverto Test' -CertStoreLocation Cert:\\CurrentUser\\My "
            f"-TextExtension @('2.5.29.37={{text}}1.3.6.1.5.5.7.3.3','2.5.29.19={{text}}'); "
            f"$pw = ConvertTo-SecureString -String 'konverto' -Force -AsPlainText; "
            f"Export-PfxCertificate -Cert $c -FilePath '{pfx}' -Password $pw | Out-Null; "
            f"Export-Certificate -Cert $c -FilePath '{cer}' | Out-Null"
        )
        run("powershell", "-NoProfile", "-Command", ps)
    run(find_sdk_tool("signtool.exe"), "sign", "/fd", "SHA256", "/a", "/f", pfx, "/p", "konverto", msix)
    print(f"Test-signiert. Zum Installieren muss {cer.name} einmalig unter "
          "'Lokaler Computer > Vertrauenswürdige Personen' importiert werden.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--msix", action="store_true", help="zusaetzlich MSIX-Paket bauen")
    ap.add_argument("--sign", action="store_true", help="MSIX mit Test-Zertifikat signieren")
    ap.add_argument("--skip-exe", action="store_true", help="vorhandenes dist/Konverto wiederverwenden")
    args = ap.parse_args()
    cfg = json.loads((PKG / "store_config.json").read_text(encoding="utf-8"))
    if not args.skip_exe:
        build_exe(cfg)
    if args.msix:
        build_msix(cfg, args.sign)


if __name__ == "__main__":
    main()
