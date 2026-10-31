"""Farben, Stylesheet und kleine Grafik-Assets."""
from __future__ import annotations

import os
from pathlib import Path

BG = "#17171a"
SURFACE = "#1f1f23"
SURFACE_2 = "#26262b"
SURFACE_3 = "#303036"
BORDER = "#34343b"
TEXT = "#ececee"
MUTED = "#9b9ba4"
ACCENT = "#e8a33d"
ACCENT_HOVER = "#f0b357"
ACCENT_TEXT = "#1a1407"
SUCCESS = "#5cb87a"
ERROR = "#e5534b"


def asset_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Konverto" / "ui"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _write_assets() -> dict[str, str]:
    d = asset_dir()
    files = {
        "chevron.svg": f'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
                       f'<path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="{MUTED}" stroke-width="1.5" '
                       f'stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "check.svg": f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">'
                     f'<path d="M3 7.2 5.8 10 11 4" fill="none" stroke="{ACCENT_TEXT}" stroke-width="2" '
                     f'stroke-linecap="round" stroke-linejoin="round"/></svg>',
    }
    out = {}
    for name, svg in files.items():
        p = d / name
        if not p.exists() or p.read_text(encoding="utf-8") != svg:
            p.write_text(svg, encoding="utf-8")
        out[name.split(".")[0]] = p.as_posix()
    return out


def stylesheet() -> str:
    a = _write_assets()
    return f"""
* {{ font-family: "Segoe UI", sans-serif; font-size: 10pt; color: {TEXT}; }}
QMainWindow, #Root {{ background: {BG}; }}
QToolTip {{ background: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER}; padding: 5px 7px; }}

#Title {{ font-size: 17pt; font-weight: 600; }}
#Subtitle {{ color: {MUTED}; }}
#Footer, #Footer QLabel {{ color: #6f6f78; font-size: 9pt; }}
#FooterLink {{ background: transparent; border: none; color: #6f6f78; font-size: 9pt; padding: 0; text-decoration: underline; }}
#FooterLink:hover {{ color: {TEXT}; }}

#Panel {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; }}
#SectionTitle {{ color: {TEXT}; font-size: 10pt; font-weight: 600; }}
#Muted {{ color: {MUTED}; }}
#QueueTitle {{ font-size: 11pt; font-weight: 600; }}
#Divider {{ background: {BORDER}; }}

#FileRow {{ background: transparent; border: none; border-bottom: 1px solid {BORDER}; border-radius: 0; }}
#FileRow:hover {{ background: {SURFACE_2}; }}
#FileName {{ font-weight: 600; }}
#FileMeta {{ color: {MUTED}; font-size: 9pt; }}
#Arrow {{ color: {MUTED}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #45454d; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}

QComboBox {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 26px 4px 8px; min-height: 18px; }}
QComboBox:hover {{ border-color: #4a4a52; }}
QComboBox:disabled {{ color: {MUTED}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url("{a['chevron']}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: {SURFACE_2}; border: 1px solid {BORDER}; padding: 2px;
    selection-background-color: {SURFACE_3}; selection-color: {TEXT}; outline: none; }}
QComboBox QAbstractItemView::item {{ min-height: 24px; padding: 0 6px; }}

QPushButton {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 4px; padding: 6px 12px; }}
QPushButton:hover {{ background: {SURFACE_3}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: #5c5c64; }}

#Ghost {{ background: transparent; border: none; color: {MUTED}; padding: 4px 6px; }}
#Ghost:hover {{ color: {TEXT}; }}
#IconBtn {{ background: transparent; border: none; color: {MUTED}; padding: 2px 6px; font-size: 10pt; }}
#IconBtn:hover {{ color: {TEXT}; background: {SURFACE_3}; }}
#LinkBtn {{ background: transparent; border: none; color: {ACCENT}; padding: 2px 4px; }}
#LinkBtn:hover {{ color: {ACCENT_HOVER}; text-decoration: underline; }}

#Chip {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 9px; font-size: 9pt; font-weight: 600; }}
#Chip:hover {{ border-color: #55555e; }}
#Chip:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: {ACCENT_TEXT}; }}

#Segment {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 0; padding: 5px 4px; font-size: 9pt; }}
#Segment[seg="first"] {{ border-top-left-radius: 4px; border-bottom-left-radius: 4px; }}
#Segment[seg="last"] {{ border-top-right-radius: 4px; border-bottom-right-radius: 4px; }}
#Segment:hover {{ background: {SURFACE_3}; }}
#Segment:checked {{ background: {SURFACE_3}; border-color: {ACCENT}; color: {ACCENT}; font-weight: 600; }}

#Primary {{ background: {ACCENT}; border: none; border-radius: 4px; padding: 10px; font-size: 11pt; font-weight: 600; color: {ACCENT_TEXT}; }}
#Primary:hover {{ background: {ACCENT_HOVER}; }}
#Primary:pressed {{ background: #d0902f; }}
#Primary:disabled {{ background: {SURFACE_3}; color: #66666e; }}
#Danger {{ background: transparent; border: 1px solid {ERROR}; color: {ERROR}; border-radius: 4px; padding: 10px; font-size: 11pt; font-weight: 600; }}
#Danger:hover {{ background: rgba(229,83,75,0.12); }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 3px; border: 1px solid #55555e; background: {SURFACE_2}; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url("{a['check']}"); }}

QSlider::groove:horizontal {{ height: 4px; background: {SURFACE_3}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {TEXT}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}

QProgressBar {{ background: {SURFACE_3}; border: none; border-radius: 1px; max-height: 3px; min-height: 3px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 1px; }}
QProgressBar[state="done"]::chunk {{ background: {SUCCESS}; }}
QProgressBar[state="error"]::chunk {{ background: {ERROR}; }}
#BigProgress {{ max-height: 4px; min-height: 4px; }}

#Toast {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-left: 3px solid {SUCCESS}; border-radius: 4px; }}
#Toast[kind="error"] {{ border-left-color: {ERROR}; }}
#PathLabel {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 4px; padding: 5px 8px; color: {MUTED}; }}
"""
