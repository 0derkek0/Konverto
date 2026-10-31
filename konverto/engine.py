"""Die eigentliche Konvertierung – komplett lokal, ohne Upload."""
from __future__ import annotations

import csv
import html as html_lib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

from PIL import Image, ImageOps, ImageSequence

from .formats import category_of, ext_of

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover - optional
    pass

ProgressFn = Callable[[float], None]

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class ConversionCancelled(Exception):
    pass


@dataclass
class Options:
    image_quality: int = 90          # JPG/WEBP/AVIF 1-100
    image_scale: int = 100           # Prozent
    audio_bitrate: str = "192k"
    video_quality: str = "balanced"  # high | balanced | small
    video_max_height: int = 0        # 0 = original
    pdf_dpi: int = 150
    merge_pdf: bool = False
    output_dir: str = ""             # leer = neben Quelldatei
    cancel: threading.Event = field(default_factory=threading.Event)


# ---------------------------------------------------------------- helpers

def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def output_path_for(src: Path, target: str, opts: Options, suffix: str = "") -> Path:
    folder = Path(opts.output_dir) if opts.output_dir else src.parent
    folder.mkdir(parents=True, exist_ok=True)
    return unique_path(folder / f"{src.stem}{suffix}.{target}")


def _check_cancel(opts: Options):
    if opts.cancel.is_set():
        raise ConversionCancelled()


_ffmpeg_cache: str | None = None


def ffmpeg_exe() -> str:
    global _ffmpeg_cache
    if _ffmpeg_cache:
        return _ffmpeg_cache
    try:
        import imageio_ffmpeg

        _ffmpeg_cache = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        _ffmpeg_cache = shutil.which("ffmpeg")
    if not _ffmpeg_cache:
        raise RuntimeError("FFmpeg wurde nicht gefunden.")
    return _ffmpeg_cache


def media_duration(src: Path) -> float:
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(src)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def run_ffmpeg(args: list[str], src: Path, out: Path, opts: Options, progress: ProgressFn):
    duration = media_duration(src)
    cmd = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-y", "-i", str(src), *args,
           "-progress", "pipe:1", "-nostats", str(out)]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW,
    )
    err_lines: list[str] = []
    t = threading.Thread(target=lambda: err_lines.extend(proc.stderr), daemon=True)
    t.start()
    try:
        for line in proc.stdout:
            if opts.cancel.is_set():
                proc.kill()
                break
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                try:
                    us = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                if duration > 0:
                    progress(min(us / 1_000_000 / duration, 0.999))
        proc.wait()
    finally:
        t.join(timeout=2)
    if opts.cancel.is_set():
        out.unlink(missing_ok=True)
        raise ConversionCancelled()
    if proc.returncode != 0:
        out.unlink(missing_ok=True)
        tail = "".join(err_lines[-6:]).strip()
        raise RuntimeError(f"FFmpeg-Fehler: {tail[-400:] or proc.returncode}")


# ---------------------------------------------------------------- audio / video

CRF = {"high": 18, "balanced": 23, "small": 28}


def audio_args(target: str, opts: Options) -> list[str]:
    br = opts.audio_bitrate
    return {
        "mp3": ["-c:a", "libmp3lame", "-b:a", br],
        "wav": ["-c:a", "pcm_s16le"],
        "flac": ["-c:a", "flac"],
        "aac": ["-c:a", "aac", "-b:a", br],
        "m4a": ["-c:a", "aac", "-b:a", br],
        "ogg": ["-c:a", "libvorbis", "-b:a", br],
        "opus": ["-c:a", "libopus", "-b:a", br],
        "wma": ["-c:a", "wmav2", "-b:a", br],
    }[target]


def scale_filter(opts: Options) -> list[str]:
    if opts.video_max_height:
        h = opts.video_max_height
        return ["-vf", f"scale=-2:'min({h},ih)'"]
    # libx264 braucht gerade Abmessungen
    return ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]


def video_args(target: str, opts: Options) -> list[str]:
    crf = CRF.get(opts.video_quality, 23)
    br = opts.audio_bitrate
    if target in ("mp4", "mkv", "mov"):
        args = ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
                *scale_filter(opts), "-c:a", "aac", "-b:a", br]
        if target in ("mp4", "mov"):
            args += ["-movflags", "+faststart"]
        return args
    if target == "avi":
        q = {"high": 2, "balanced": 4, "small": 7}[opts.video_quality]
        return ["-c:v", "mpeg4", "-q:v", str(q), *scale_filter(opts), "-c:a", "libmp3lame", "-b:a", br]
    if target == "webm":
        return ["-c:v", "libvpx-vp9", "-crf", str(crf + 10), "-b:v", "0", "-deadline", "good",
                "-cpu-used", "4", "-row-mt", "1", *scale_filter(opts), "-c:a", "libopus", "-b:a", br]
    if target == "gif":
        h = opts.video_max_height or 480
        width = {"high": 640, "balanced": 480, "small": 320}[opts.video_quality]
        fps = {"high": 20, "balanced": 15, "small": 10}[opts.video_quality]
        scale = f"scale='min({width},iw)':-1:flags=lanczos" if not opts.video_max_height else f"scale=-1:'min({h},ih)':flags=lanczos"
        return ["-vf", f"fps={fps},{scale},split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a",
                "-loop", "0"]
    raise ValueError(target)


def convert_media(src: Path, target: str, opts: Options, progress: ProgressFn) -> Path:
    out = output_path_for(src, target, opts)
    if target in ("mp3", "wav", "flac", "aac", "m4a", "ogg", "opus", "wma"):
        args = ["-vn", "-map", "0:a:0?", *audio_args(target, opts)]
    else:
        args = video_args(target, opts)
        if target != "gif":
            args = ["-map", "0:v:0", "-map", "0:a?", *args]
    run_ffmpeg(args, src, out, opts, progress)
    return out


# ---------------------------------------------------------------- images

def _flatten(img: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        base = Image.new("RGB", img.size, bg)
        base.paste(img, mask=img.split()[-1])
        return base
    return img.convert("RGB")


def _scaled(img: Image.Image, opts: Options) -> Image.Image:
    if opts.image_scale and opts.image_scale != 100:
        f = opts.image_scale / 100
        w, h = max(1, round(img.width * f)), max(1, round(img.height * f))
        return img.resize((w, h), Image.LANCZOS)
    return img


def open_image(src: Path) -> Image.Image:
    img = Image.open(src)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


def save_image(img: Image.Image, out: Path, target: str, opts: Options):
    q = opts.image_quality
    if target == "jpg":
        _flatten(img).save(out, "JPEG", quality=q, optimize=True, progressive=True, subsampling=0 if q >= 90 else 2)
    elif target == "png":
        img = img if img.mode in ("RGB", "RGBA", "L", "LA", "P") else img.convert("RGBA")
        img.save(out, "PNG", optimize=True)
    elif target == "webp":
        img = img if img.mode in ("RGB", "RGBA") else img.convert("RGBA")
        img.save(out, "WEBP", quality=q, method=6)
    elif target == "avif":
        img = img if img.mode in ("RGB", "RGBA") else img.convert("RGBA")
        img.save(out, "AVIF", quality=q)
    elif target == "bmp":
        _flatten(img).save(out, "BMP")
    elif target == "tiff":
        img = img if img.mode in ("RGB", "RGBA", "L", "CMYK") else img.convert("RGBA")
        img.save(out, "TIFF", compression="tiff_lzw")
    elif target == "gif":
        img.convert("RGBA").save(out, "GIF")
    elif target == "ico":
        img = img.convert("RGBA")
        side = max(img.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
        sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= max(side, 16)]
        square.save(out, "ICO", sizes=sizes)
    elif target == "pdf":
        _flatten(img).save(out, "PDF", resolution=opts.pdf_dpi)
    else:
        raise ValueError(f"Unbekanntes Bildformat: {target}")


def convert_image(src: Path, target: str, opts: Options, progress: ProgressFn) -> Path:
    if target in ("mp4", "webm"):  # animiertes GIF -> Video
        return convert_media(src, target, opts, progress)
    out = output_path_for(src, target, opts)
    img = open_image(src)
    progress(0.3)
    animated = getattr(img, "n_frames", 1) > 1
    if animated and target in ("gif", "webp"):
        frames = [_scaled(f.convert("RGBA"), opts) for f in ImageSequence.Iterator(img)]
        kw = {"save_all": True, "append_images": frames[1:], "loop": img.info.get("loop", 0),
              "duration": img.info.get("duration", 100)}
        if target == "webp":
            kw["quality"] = opts.image_quality
        frames[0].save(out, target.upper(), **kw)
    elif animated and target == "pdf":
        pages = [_flatten(_scaled(f.convert("RGBA"), opts)) for f in ImageSequence.Iterator(img)]
        pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=opts.pdf_dpi)
    else:
        save_image(_scaled(img, opts), out, target, opts)
    progress(1.0)
    return out


# ---------------------------------------------------------------- PDF

def convert_pdf(src: Path, target: str, opts: Options, progress: ProgressFn) -> Path:
    import pymupdf

    doc = pymupdf.open(src)
    n = len(doc)
    if target in ("png", "jpg"):
        if n == 1:
            outs = [output_path_for(src, target, opts)]
        else:
            folder = Path(opts.output_dir) if opts.output_dir else src.parent
            folder = unique_path(folder / f"{src.stem}_{target}")
            folder.mkdir(parents=True)
            outs = [folder / f"{src.stem}_Seite_{i + 1:03d}.{target}" for i in range(n)]
        for i, page in enumerate(doc):
            _check_cancel(opts)
            pix = page.get_pixmap(dpi=opts.pdf_dpi, alpha=False)
            if target == "png":
                pix.save(outs[i])
            else:
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                img.save(outs[i], "JPEG", quality=opts.image_quality, optimize=True)
            progress((i + 1) / n)
        return outs[0] if n == 1 else outs[0].parent
    out = output_path_for(src, target, opts)
    if target == "txt":
        parts = []
        for i, page in enumerate(doc):
            _check_cancel(opts)
            parts.append(page.get_text())
            progress((i + 1) / n)
        out.write_text("\n\f\n".join(parts), encoding="utf-8")
    elif target == "html":
        parts = []
        for i, page in enumerate(doc):
            _check_cancel(opts)
            parts.append(page.get_text("xhtml"))
            progress((i + 1) / n)
        out.write_text(_html_page(src.stem, "\n<hr>\n".join(parts)), encoding="utf-8")
    elif target == "docx":
        from docx import Document

        d = Document()
        for i, page in enumerate(doc):
            _check_cancel(opts)
            for block in page.get_text("blocks"):
                text = block[4].strip()
                if text and block[6] == 0:
                    d.add_paragraph(re.sub(r"\s*\n\s*", " ", text))
            if i < n - 1:
                d.add_page_break()
            progress((i + 1) / n)
        d.save(out)
    else:
        raise ValueError(target)
    return out


# ---------------------------------------------------------------- Dokumente

BASE_CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.45; color: #111; }
h1 { font-size: 20pt; } h2 { font-size: 16pt; } h3 { font-size: 13pt; }
pre, code { font-family: monospace; font-size: 9.5pt; }
pre { background: #f3f3f3; padding: 6px; }
table { border-collapse: collapse; }
td, th { border: 1px solid #999; padding: 3px 6px; }
"""


def _html_page(title: str, body: str) -> str:
    return (f"<!doctype html>\n<html><head><meta charset='utf-8'><title>{html_lib.escape(title)}</title>"
            f"<style>{BASE_CSS}</style></head><body>\n{body}\n</body></html>")


def _read_text(src: Path) -> str:
    raw = src.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _docx_to_html(src: Path) -> str:
    from docx import Document

    d = Document(src)
    out = []
    body = d.element.body
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, d)
            runs = []
            for r in p.runs:
                t = html_lib.escape(r.text)
                if not t:
                    continue
                if r.bold:
                    t = f"<b>{t}</b>"
                if r.italic:
                    t = f"<i>{t}</i>"
                if r.underline:
                    t = f"<u>{t}</u>"
                runs.append(t)
            content = "".join(runs)
            style = (p.style.name if p.style is not None else "") or ""
            m = re.match(r"(Heading|Überschrift)\s*(\d)", style)
            if style == "Title":
                out.append(f"<h1>{content}</h1>")
            elif m:
                lvl = min(int(m.group(2)), 6)
                out.append(f"<h{lvl}>{content}</h{lvl}>")
            elif "List" in style or "Liste" in style:
                out.append(f"<p>• {content}</p>")
            else:
                out.append(f"<p>{content or '&nbsp;'}</p>")
        elif tag == "tbl":
            t = Table(child, d)
            rows = []
            for row in t.rows:
                cells = "".join(f"<td>{html_lib.escape(c.text)}</td>" for c in row.cells)
                rows.append(f"<tr>{cells}</tr>")
            out.append(f"<table>{''.join(rows)}</table>")
    return _html_page(src.stem, "\n".join(out))


def _doc_to_html(src: Path) -> str:
    e = ext_of(src)
    if e == "docx":
        return _docx_to_html(src)
    if e == "txt":
        paras = re.split(r"\n\s*\n", _read_text(src))
        body = "\n".join(f"<p>{html_lib.escape(p).replace(chr(10), '<br>')}</p>" for p in paras)
        return _html_page(src.stem, body)
    if e == "md":
        import markdown

        body = markdown.markdown(_read_text(src), extensions=["tables", "fenced_code", "sane_lists"])
        return _html_page(src.stem, body)
    if e == "html":
        return _read_text(src)
    raise ValueError(e)


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "table", "section", "article"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self.parts)).strip() + "\n"


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return p.text()


def html_to_pdf(html: str, out: Path, opts: Options, base_dir: Path):
    import pymupdf

    # Story kennt kein <style> im head zuverlaessig -> CSS separat uebergeben
    story = pymupdf.Story(html=html, user_css=BASE_CSS, archive=str(base_dir))
    writer = pymupdf.DocumentWriter(str(out))
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (56, 56, -56, -56)
    more = 1
    while more:
        _check_cancel(opts)
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()


def text_to_docx(text: str, out: Path, md: bool = False):
    from docx import Document

    d = Document()
    for block in re.split(r"\n\s*\n", text):
        block = block.strip("\n")
        if not block:
            continue
        if md:
            m = re.match(r"^(#{1,6})\s+(.*)", block)
            if m and "\n" not in block:
                d.add_heading(m.group(2), level=min(len(m.group(1)), 9))
                continue
        d.add_paragraph(block)
    d.save(out)


def convert_document(src: Path, target: str, opts: Options, progress: ProgressFn) -> Path:
    out = output_path_for(src, target, opts)
    e = ext_of(src)
    progress(0.1)
    if target == "docx":
        if e == "html":
            text_to_docx(html_to_text(_read_text(src)), out)
        else:
            text_to_docx(_read_text(src), out, md=(e == "md"))
    else:
        html = _doc_to_html(src)
        progress(0.4)
        if target == "html":
            out.write_text(html, encoding="utf-8")
        elif target == "txt":
            out.write_text(_read_text(src) if e == "md" else html_to_text(html), encoding="utf-8")
        elif target == "pdf":
            html_to_pdf(html, out, opts, src.parent)
        else:
            raise ValueError(target)
    progress(1.0)
    return out


# ---------------------------------------------------------------- Daten

def _load_table(src: Path) -> list[list]:
    e = ext_of(src)
    if e == "csv":
        text = _read_text(src)
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        return [row for row in csv.reader(io.StringIO(text), dialect)]
    if e == "xlsx":
        from openpyxl import load_workbook

        wb = load_workbook(src, read_only=True, data_only=True)
        ws = wb.active
        rows = [["" if v is None else v for v in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
        while rows and all(v == "" for v in rows[-1]):
            rows.pop()
        return rows
    if e == "json":
        data = json.loads(_read_text(src))
        if isinstance(data, dict):
            # {"a": [...]} -> erste Liste nehmen, sonst dict als eine Zeile
            lists = [v for v in data.values() if isinstance(v, list)]
            data = lists[0] if lists else [data]
        if not isinstance(data, list):
            data = [data]
        if data and all(isinstance(r, dict) for r in data):
            keys: list[str] = []
            for r in data:
                for k in r:
                    if k not in keys:
                        keys.append(k)
            return [keys] + [[_cell(r.get(k, "")) for k in keys] for r in data]
        return [[_cell(v) for v in r] if isinstance(r, list) else [_cell(r)] for r in data]
    raise ValueError(e)


def _cell(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


def convert_data(src: Path, target: str, opts: Options, progress: ProgressFn) -> Path:
    out = output_path_for(src, target, opts)
    rows = _load_table(src)
    progress(0.5)
    if target == "csv":
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, delimiter=";").writerows(rows)
    elif target == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = src.stem[:31] or "Tabelle"
        for row in rows:
            ws.append([_num(v) for v in row])
        if rows:
            for c in ws[1]:
                c.font = Font(bold=True)
            for col in ws.columns:
                width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(width + 2, 60)
        wb.save(out)
    elif target == "json":
        if len(rows) >= 2:
            header = [str(h) for h in rows[0]]
            data = [dict(zip(header, [_num(v) for v in r])) for r in rows[1:]]
        else:
            data = rows
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    else:
        raise ValueError(target)
    progress(1.0)
    return out


def _num(v):
    if isinstance(v, str):
        s = v.strip()
        if re.fullmatch(r"-?\d+", s) and not (len(s) > 1 and s.lstrip("-").startswith("0")):
            try:
                return int(s)
            except ValueError:
                return v
        if re.fullmatch(r"-?\d+[.,]\d+", s):
            try:
                return float(s.replace(",", "."))
            except ValueError:
                return v
    return v


# ---------------------------------------------------------------- Dispatcher

def convert(src: str | Path, target: str, opts: Options, progress: ProgressFn = lambda p: None) -> Path:
    src = Path(src)
    _check_cancel(opts)
    cat = category_of(src)
    fn = {
        "video": convert_media,
        "audio": convert_media,
        "image": convert_image,
        "pdf": convert_pdf,
        "document": convert_document,
        "data": convert_data,
    }.get(cat)
    if fn is None:
        raise ValueError("Dateityp wird nicht unterstützt")
    result = fn(src, target, opts, progress)
    progress(1.0)
    return result


def merge_to_pdf(sources: list[Path], opts: Options, progress: ProgressFn, name: str = "Zusammengefuegt") -> Path:
    """Bilder, PDFs und Dokumente in eine einzige PDF packen."""
    import pymupdf

    folder = Path(opts.output_dir) if opts.output_dir else sources[0].parent
    out = unique_path(folder / f"{name}.pdf")
    result = pymupdf.open()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_opts = Options(**{**opts.__dict__, "output_dir": tmp, "cancel": opts.cancel})
        for i, src in enumerate(sources):
            _check_cancel(opts)
            cat = category_of(src)
            if cat == "pdf":
                part = src
            elif cat == "image":
                part = output_path_for(src, "pdf", tmp_opts)
                img = open_image(src)
                if getattr(img, "n_frames", 1) > 1:
                    img.seek(0)
                save_image(_scaled(img, opts), part, "pdf", opts)
            elif cat == "document":
                part = convert_document(src, "pdf", tmp_opts, lambda p: None)
            else:
                continue
            with pymupdf.open(part) as d:
                result.insert_pdf(d)
            progress((i + 1) / len(sources))
    if len(result) == 0:
        raise RuntimeError("Keine Datei konnte in die PDF übernommen werden.")
    result.save(out, garbage=3, deflate=True)
    result.close()
    return out


def reveal_in_explorer(path: Path):
    if sys.platform == "win32":
        if path.is_dir():
            os.startfile(path)
        else:
            subprocess.Popen(["explorer", "/select,", str(path)], creationflags=CREATE_NO_WINDOW)
