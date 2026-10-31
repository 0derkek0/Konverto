"""Welche Formate es gibt und was wohin konvertiert werden kann."""
from __future__ import annotations

from pathlib import Path

from PIL import features

VIDEO_IN = ["mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "m4v", "mpeg", "mpg", "3gp", "ts", "mts"]
AUDIO_IN = ["mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "opus", "aiff", "aif", "amr"]
IMAGE_IN = ["png", "jpg", "jpeg", "jfif", "webp", "bmp", "gif", "tiff", "tif", "ico", "heic", "heif", "avif", "tga"]
PDF_IN = ["pdf"]
DOC_IN = ["docx", "txt", "md", "html", "htm"]
DATA_IN = ["csv", "xlsx", "json"]

VIDEO_OUT = ["mp4", "mkv", "mov", "avi", "webm", "gif"]
AUDIO_OUT = ["mp3", "wav", "flac", "aac", "m4a", "ogg", "opus", "wma"]
IMAGE_OUT = ["png", "jpg", "webp", "bmp", "gif", "tiff", "ico", "pdf"]
if features.check("avif"):
    IMAGE_OUT.insert(3, "avif")

CATEGORY_LABELS = {
    "video": "Video",
    "audio": "Audio",
    "image": "Bild",
    "pdf": "PDF",
    "document": "Dokument",
    "data": "Daten",
}

CATEGORY_COLORS = {
    "video": "#d98aa0",
    "audio": "#d9b36f",
    "image": "#7fc79a",
    "pdf": "#d98a7f",
    "document": "#86aede",
    "data": "#ad9cd6",
}

# Beschreibungen fuer Tooltips
FORMAT_HINTS = {
    "mp4": "Video (H.264) – läuft überall",
    "mkv": "Video (H.264) im Matroska-Container",
    "mov": "Video (H.264) für Apple/Final Cut",
    "avi": "Klassisches AVI (MPEG-4)",
    "webm": "Web-Video (VP9 + Opus)",
    "gif": "Animiertes GIF",
    "mp3": "Audio – universell",
    "wav": "Audio – unkomprimiert",
    "flac": "Audio – verlustfrei komprimiert",
    "aac": "Audio – AAC roh",
    "m4a": "Audio – AAC im MP4-Container",
    "ogg": "Audio – Ogg Vorbis",
    "opus": "Audio – Opus (sehr effizient)",
    "wma": "Audio – Windows Media",
    "png": "Bild – verlustfrei, Transparenz",
    "jpg": "Bild – klein, Fotos",
    "webp": "Bild – modern & klein",
    "avif": "Bild – sehr effizient",
    "bmp": "Bild – unkomprimiert",
    "tiff": "Bild – Druck/Archiv",
    "ico": "Windows-Icon (bis 256px)",
    "pdf": "PDF-Dokument",
    "txt": "Reiner Text",
    "html": "Webseite",
    "docx": "Word-Dokument",
    "csv": "Tabelle (CSV)",
    "xlsx": "Excel-Tabelle",
    "json": "JSON-Daten",
}


def ext_of(path: str | Path) -> str:
    e = Path(path).suffix.lower().lstrip(".")
    return {"jpeg": "jpg", "jfif": "jpg", "tif": "tiff", "htm": "html", "aif": "aiff", "heif": "heic"}.get(e, e)


def category_of(path: str | Path) -> str | None:
    e = Path(path).suffix.lower().lstrip(".")
    if e in VIDEO_IN:
        return "video"
    if e in AUDIO_IN:
        return "audio"
    if e in IMAGE_IN:
        return "image"
    if e in PDF_IN:
        return "pdf"
    if e in DOC_IN:
        return "document"
    if e in DATA_IN:
        return "data"
    return None


def targets_for(path: str | Path) -> list[str]:
    """Alle Zielformate fuer eine Datei (ohne das eigene Format)."""
    cat = category_of(path)
    src = ext_of(path)
    if cat == "video":
        out = VIDEO_OUT + AUDIO_OUT
    elif cat == "audio":
        out = list(AUDIO_OUT)
    elif cat == "image":
        out = list(IMAGE_OUT)
        if src == "gif":
            out += ["mp4", "webm"]
    elif cat == "pdf":
        out = ["png", "jpg", "txt", "docx", "html"]
    elif cat == "document":
        out = {
            "docx": ["pdf", "txt", "html"],
            "txt": ["pdf", "docx", "html"],
            "md": ["pdf", "html", "docx", "txt"],
            "html": ["pdf", "txt", "docx"],
        }.get(src, [])
    elif cat == "data":
        out = ["csv", "xlsx", "json"]
    else:
        out = []
    return [t for t in out if t != src]


def all_input_patterns() -> str:
    exts = VIDEO_IN + AUDIO_IN + IMAGE_IN + PDF_IN + DOC_IN + DATA_IN
    return " ".join(f"*.{e}" for e in exts)
