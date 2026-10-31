"""Hauptfenster von Konverto."""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
                               QSlider, QVBoxLayout, QWidget)

from . import APP_NAME, APP_VERSION, SOURCE_URL, engine, theme
from .formats import (AUDIO_OUT, FORMAT_HINTS, IMAGE_OUT, VIDEO_OUT, all_input_patterns, category_of,
                      targets_for)
from .widgets import DropZone, FileRow, FlowLayout, Segmented, Toast, app_icon, draw_logo

DEFAULT_PREFS = {
    "video": ["mp4", "mp3"],
    "audio": ["mp3", "wav"],
    "image": ["jpg", "png"],
    "pdf": ["png"],
    "document": ["pdf", "txt"],
    "data": ["xlsx", "csv"],
}

FORMAT_ORDER: list[str] = []
for _f in VIDEO_OUT + AUDIO_OUT + IMAGE_OUT + ["txt", "html", "docx", "csv", "xlsx", "json"]:
    if _f not in FORMAT_ORDER:
        FORMAT_ORDER.append(_f)


class Bridge(QObject):
    started = Signal(object)
    progress = Signal(object, float)
    done = Signal(object, object)
    failed = Signal(object, str)
    finished = Signal()


def section(title: str) -> QLabel:
    lbl = QLabel(title.upper())
    lbl.setObjectName("SectionTitle")
    return lbl


def field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Muted")
    return lbl


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} – Datei-Konverter")
        self.setWindowIcon(app_icon())
        self.resize(1220, 800)
        self.setMinimumSize(1000, 660)
        self.setAcceptDrops(True)
        self.settings = QSettings(APP_NAME, APP_NAME)
        self.rows: list[FileRow] = []
        self.chips: dict[str, QPushButton] = {}
        self.global_target: str | None = None
        self.opts: engine.Options | None = None
        self.running = False
        self.bridge = Bridge()
        self.bridge.started.connect(self._on_started)
        self.bridge.progress.connect(self._on_progress)
        self.bridge.done.connect(self._on_done)
        self.bridge.failed.connect(self._on_failed)
        self.bridge.finished.connect(self._on_finished)

        root = QWidget(objectName="Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 18, 24, 10)
        outer.setSpacing(16)
        outer.addLayout(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addLayout(self._build_left(), 1)
        self.panel = self._build_panel()
        body.addWidget(self.panel)
        outer.addLayout(body, 1)
        outer.addWidget(self._build_footer())

        self.toast = Toast(root)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.pick_files)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.start)
        self._refresh()

    # ------------------------------------------------------------ Aufbau

    def _build_header(self):
        lay = QHBoxLayout()
        lay.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(draw_logo(72))
        logo.setScaledContents(True)
        logo.setFixedSize(36, 36)
        lay.addWidget(logo)
        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        lay.addWidget(title)
        sub = QLabel("Dateien umwandeln, direkt auf deinem PC")
        sub.setObjectName("Subtitle")
        sub.setStyleSheet("padding-top: 5px;")
        lay.addSpacing(6)
        lay.addWidget(sub, 0, Qt.AlignVCenter)
        lay.addStretch(1)
        return lay

    def _build_footer(self):
        foot = QWidget(objectName="Footer")
        lay = QHBoxLayout(foot)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.addWidget(QLabel("Erstellt von DerKeK"))
        lay.addStretch(1)
        lay.addWidget(QLabel(f"Version {APP_VERSION}  ·"))
        src = QPushButton("Quellcode", objectName="FooterLink", cursor=Qt.PointingHandCursor)
        src.setToolTip(SOURCE_URL)
        src.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(SOURCE_URL)))
        lay.addWidget(src)
        lay.addWidget(QLabel("·"))
        lic = QPushButton("Lizenzen", objectName="FooterLink", cursor=Qt.PointingHandCursor)
        lic.clicked.connect(self.show_licenses)
        lay.addWidget(lic)
        return foot

    def show_licenses(self):
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        f = base / "THIRD_PARTY_NOTICES.txt"
        text = f.read_text(encoding="utf-8") if f.exists() else "Lizenzhinweise nicht gefunden."
        dlg = QDialog(self)
        dlg.setWindowTitle("Lizenzen")
        dlg.resize(640, 520)
        dlg.setStyleSheet(f"QDialog {{ background: {theme.BG}; }}")
        lay = QVBoxLayout(dlg)
        head = QLabel(f"{APP_NAME} {APP_VERSION}, erstellt von DerKeK.<br>"
                      f"Konverto ist freie Software unter der GNU AGPL-3.0. Quellcode: "
                      f"<a href='{SOURCE_URL}' style='color:{theme.ACCENT}'>{SOURCE_URL}</a><br><br>"
                      f"Verwendete Open-Source-Komponenten:")
        head.setWordWrap(True)
        head.setOpenExternalLinks(True)
        view = QPlainTextEdit(text, readOnly=True)
        view.setStyleSheet(f"background: {theme.SURFACE}; border: 1px solid {theme.BORDER}; font-family: Consolas; font-size: 9pt;")
        ok = QPushButton("Schließen", cursor=Qt.PointingHandCursor)
        ok.clicked.connect(dlg.accept)
        lay.addWidget(head)
        lay.addWidget(view, 1)
        lay.addWidget(ok, 0, Qt.AlignRight)
        dlg.exec()

    def _build_left(self):
        col = QVBoxLayout()
        col.setSpacing(14)
        self.dropzone = DropZone()
        self.dropzone.clicked.connect(self.pick_files)
        col.addWidget(self.dropzone, 1)

        self.queue_frame = QFrame(objectName="Panel")
        q = QVBoxLayout(self.queue_frame)
        q.setContentsMargins(16, 14, 10, 12)
        q.setSpacing(10)
        head = QHBoxLayout()
        self.queue_title = QLabel("Warteschlange", objectName="QueueTitle")
        self.queue_count = QLabel(objectName="Muted")
        head.addWidget(self.queue_title)
        head.addWidget(self.queue_count)
        head.addStretch(1)
        self.clear_done_btn = QPushButton("Fertige entfernen", objectName="Ghost", cursor=Qt.PointingHandCursor)
        self.clear_done_btn.clicked.connect(self.clear_done)
        self.clear_btn = QPushButton("Alle entfernen", objectName="Ghost", cursor=Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_all)
        head.addWidget(self.clear_done_btn)
        head.addWidget(self.clear_btn)
        q.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.addStretch(1)
        scroll.setWidget(container)
        q.addWidget(scroll, 1)
        col.addWidget(self.queue_frame, 1)
        return col

    def _build_panel(self):
        panel = QFrame(objectName="Panel")
        panel.setFixedWidth(330)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(18, 16, 14, 12)
        lay.setSpacing(18)

        def group(title: str) -> tuple[QWidget, QVBoxLayout]:
            box = QWidget()
            v = QVBoxLayout(box)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(7)
            v.addWidget(section(title))
            lay.addWidget(box)
            return box, v

        def sub(v: QVBoxLayout) -> tuple[QWidget, QVBoxLayout]:
            w = QWidget()
            sv = QVBoxLayout(w)
            sv.setContentsMargins(0, 0, 0, 0)
            sv.setSpacing(5)
            v.addWidget(w)
            return w, sv

        s = self.settings

        # Zielformat
        _, v = group("Alle umwandeln in")
        self.chip_host = QWidget()
        self.chip_flow = FlowLayout(self.chip_host, spacing=5)
        v.addWidget(self.chip_host)
        tip = QLabel("Oder rechts neben jeder Datei einzeln wählen.")
        tip.setObjectName("Muted")
        tip.setStyleSheet("font-size: 9pt;")
        v.addWidget(tip)

        # Bild
        self.grp_image, v = group("Bild")
        self.quality_box, sv = sub(v)
        qrow = QHBoxLayout()
        qrow.addWidget(field_label("Qualität"))
        qrow.addStretch(1)
        self.quality_val = QLabel(objectName="Muted")
        qrow.addWidget(self.quality_val)
        sv.addLayout(qrow)
        self.quality = QSlider(Qt.Horizontal)
        self.quality.setRange(10, 100)
        self.quality.setValue(int(s.value("quality", 90)))
        self.quality.setCursor(Qt.PointingHandCursor)
        self.quality.valueChanged.connect(lambda val: self.quality_val.setText(f"{val} %"))
        self.quality_val.setText(f"{self.quality.value()} %")
        sv.addWidget(self.quality)
        self.scale_box, sv = sub(v)
        sv.addWidget(field_label("Größe"))
        self.scale = Segmented([("100 %", 100), ("75 %", 75), ("50 %", 50), ("25 %", 25)], int(s.value("scale", 100)))
        sv.addWidget(self.scale)

        # Video
        self.grp_video, v = group("Video")
        v.addWidget(field_label("Qualität"))
        self.vquality = Segmented([("Hoch", "high"), ("Mittel", "balanced"), ("Klein", "small")],
                                  s.value("vquality", "balanced"))
        v.addWidget(self.vquality)
        v.addWidget(field_label("Max. Auflösung"))
        self.vres = QComboBox(cursor=Qt.PointingHandCursor)
        for label, val in [("Original", 0), ("2160p (4K)", 2160), ("1440p", 1440), ("1080p (Full HD)", 1080),
                           ("720p", 720), ("480p", 480), ("360p", 360)]:
            self.vres.addItem(label, val)
        self.vres.setCurrentIndex(max(0, self.vres.findData(int(s.value("vres", 0)))))
        v.addWidget(self.vres)

        # Audio
        self.grp_audio, v = group("Audio")
        v.addWidget(field_label("Bitrate"))
        self.bitrate = Segmented([("128k", "128k"), ("192k", "192k"), ("256k", "256k"), ("320k", "320k")],
                                 s.value("bitrate", "192k"))
        v.addWidget(self.bitrate)

        # PDF
        self.grp_pdf, v = group("PDF")
        self.dpi_box, sv = sub(v)
        sv.addWidget(field_label("Auflösung der Bilder (DPI)"))
        self.dpi = Segmented([("72", 72), ("150", 150), ("300", 300)], int(s.value("dpi", 150)))
        sv.addWidget(self.dpi)
        self.merge = QCheckBox("Alles in eine PDF zusammenfügen", cursor=Qt.PointingHandCursor)
        self.merge.setToolTip("Gilt für alle Dateien mit Ziel PDF (Bilder, PDFs, Dokumente)")
        self.merge.setChecked(s.value("merge", "false") == "true")
        v.addWidget(self.merge)

        # Speicherort
        _, v = group("Speichern")
        lay = v
        self.out_mode = Segmented([("Neben Original", "same"), ("Eigener Ordner", "custom")], s.value("out_mode", "same"))
        self.out_mode.changed.connect(lambda _: self._refresh_out())
        lay.addWidget(self.out_mode)
        prow = QHBoxLayout()
        self.out_label = QLabel(objectName="PathLabel")
        self.out_label.setMinimumWidth(10)
        self.out_dir = s.value("out_dir", str(Path.home() / "Downloads"))
        change = QPushButton("Ändern", cursor=Qt.PointingHandCursor)
        change.clicked.connect(self.pick_out_dir)
        prow.addWidget(self.out_label, 1)
        prow.addWidget(change)
        self.out_row = QWidget()
        self.out_row.setLayout(prow)
        prow.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.out_row)
        inner.layout().addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Button unten
        foot = QVBoxLayout()
        foot.setContentsMargins(18, 12, 18, 16)
        foot.setSpacing(8)
        line = QFrame(objectName="Divider")
        line.setFixedHeight(1)
        outer.addWidget(line)
        self.total_progress = QProgressBar(objectName="BigProgress")
        self.total_progress.setRange(0, 1000)
        self.total_progress.setTextVisible(False)
        self.status = QLabel(objectName="Muted")
        self.status.setWordWrap(True)
        self.go = QPushButton("Konvertieren", objectName="Primary", cursor=Qt.PointingHandCursor)
        self.go.clicked.connect(self.start)
        self.cancel_btn = QPushButton("Abbrechen", objectName="Danger", cursor=Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.cancel)
        self.cancel_btn.hide()
        foot.addWidget(self.status)
        foot.addWidget(self.total_progress)
        foot.addWidget(self.go)
        foot.addWidget(self.cancel_btn)
        outer.addLayout(foot)
        self._refresh_out()
        return panel

    # ------------------------------------------------------------ Dateien

    def pick_files(self):
        if self.running:
            return
        start = self.settings.value("last_dir", str(Path.home()))
        files, _ = QFileDialog.getOpenFileNames(
            self, "Dateien auswählen", start,
            f"Alle unterstützten Dateien ({all_input_patterns()});;Alle Dateien (*)")
        if files:
            self.settings.setValue("last_dir", str(Path(files[0]).parent))
            self.add_paths([Path(f) for f in files])

    def pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Speicherort wählen", self.out_dir)
        if d:
            self.out_dir = d
            self.out_mode.set_value("custom")
            self._refresh_out()

    def _refresh_out(self):
        custom = self.out_mode.value() == "custom"
        self.out_row.setVisible(custom)
        fm = self.out_label.fontMetrics()
        self.out_label.setText(fm.elidedText(self.out_dir, Qt.ElideMiddle, 220))
        self.out_label.setToolTip(self.out_dir)

    def add_paths(self, paths: list[Path]):
        files: list[Path] = []
        for p in paths:
            if p.is_dir():
                files += sorted(f for f in p.rglob("*") if f.is_file() and category_of(f))
            elif p.is_file():
                files.append(p)
        existing = {r.path.resolve() for r in self.rows if r.state != "done"}
        skipped = 0
        added = 0
        for f in files:
            cat = category_of(f)
            targets = targets_for(f)
            if not cat or not targets:
                skipped += 1
                continue
            if f.resolve() in existing:
                continue
            existing.add(f.resolve())
            default = None
            if self.global_target in targets:
                default = self.global_target
            else:
                default = next((t for t in DEFAULT_PREFS.get(cat, []) if t in targets), targets[0])
            row = FileRow(f, cat, targets, default)
            row.removed.connect(self.remove_row)
            row.target_changed.connect(lambda _: self._refresh())
            row.open_btn.clicked.connect(lambda _=False, r=row: r.result and engine.reveal_in_explorer(r.result))
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
            self.rows.append(row)
            added += 1
        self._refresh()
        if skipped:
            self.toast.show_toast(f"{skipped} Datei(en) übersprungen – Format wird nicht unterstützt.", "error")

    def remove_row(self, row: FileRow):
        if self.running:
            return
        self.rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._refresh()

    def clear_all(self):
        for r in list(self.rows):
            self.remove_row(r)

    def clear_done(self):
        for r in [r for r in self.rows if r.state == "done"]:
            self.remove_row(r)

    # ------------------------------------------------------------ Zielformat-Chips

    def _rebuild_chips(self):
        counts: dict[str, int] = {}
        for r in self.rows:
            for i in range(r.combo.count()):
                t = r.combo.itemData(i)
                counts[t] = counts.get(t, 0) + 1
        wanted = sorted(counts, key=lambda t: FORMAT_ORDER.index(t) if t in FORMAT_ORDER else 999)
        if list(self.chips) != wanted:
            for b in self.chips.values():
                self.chip_flow.removeWidget(b)
                b.deleteLater()
            self.chips.clear()
            for t in wanted:
                b = QPushButton(t.upper(), objectName="Chip", cursor=Qt.PointingHandCursor)
                b.setCheckable(True)
                b.clicked.connect(lambda _=False, t=t: self.apply_global(t))
                self.chip_flow.addWidget(b)
                self.chips[t] = b
        n = len(self.rows)
        for t, b in self.chips.items():
            hint = FORMAT_HINTS.get(t, t.upper())
            b.setToolTip(f"{hint}\nMöglich für {counts[t]} von {n} Datei(en)")
            active = [r for r in self.rows if r.supports(t)]
            b.setChecked(bool(active) and all(r.target == t for r in active) and t == self.global_target)
        self.chip_host.updateGeometry()

    def apply_global(self, t: str):
        if self.running:
            return
        self.global_target = t
        for r in self.rows:
            if r.state != "running":
                r.set_target(t)
        self._refresh()

    # ------------------------------------------------------------ Status

    def _update_sections(self):
        """Nur die Einstellungen zeigen, die fuer die aktuellen Dateien/Ziele etwas bewirken."""
        jobs = [(r.category, r.target) for r in self.rows]
        lossy_img = any(t in ("jpg", "webp", "avif") and c in ("image", "pdf") for c, t in jobs)
        resize_img = any(c == "image" and t not in ("mp4", "webm") for c, t in jobs)
        video = any(t in VIDEO_OUT and (c == "video" or (c == "image" and t in ("mp4", "webm"))) for c, t in jobs)
        audio = any(c in ("video", "audio") and t not in ("wav", "flac", "gif") for c, t in jobs)
        pdf_render = any(c == "pdf" and t in ("png", "jpg") for c, t in jobs)
        to_pdf = sum(1 for c, t in jobs if t == "pdf" and c in ("image", "pdf", "document"))
        self.quality_box.setVisible(lossy_img)
        self.scale_box.setVisible(resize_img)
        self.grp_image.setVisible(lossy_img or resize_img)
        self.grp_video.setVisible(video)
        self.grp_audio.setVisible(audio)
        self.dpi_box.setVisible(pdf_render)
        self.merge.setVisible(to_pdf >= 2)
        self.grp_pdf.setVisible(pdf_render or to_pdf >= 2)

    def _refresh(self):
        has = bool(self.rows)
        self.queue_frame.setVisible(has)
        self.panel.setVisible(has)
        self.dropzone.set_compact(has)
        self._rebuild_chips()
        self._update_sections()
        todo = [r for r in self.rows if r.state != "done"]
        self.queue_count.setText(f"· {len(self.rows)} Datei{'en' if len(self.rows) != 1 else ''}" if has else "")
        self.clear_done_btn.setVisible(any(r.state == "done" for r in self.rows))
        if not self.running:
            self.go.setEnabled(bool(todo))
            self.go.setText(f"{len(todo)} Datei{'en' if len(todo) != 1 else ''} konvertieren" if todo else "Konvertieren")
            if not has:
                self.status.setText("Noch keine Dateien ausgewählt.")
                self.total_progress.setValue(0)
            elif todo:
                self.status.setText("Bereit. Strg+Enter startet die Konvertierung.")

    # ------------------------------------------------------------ Konvertierung

    def _collect_options(self) -> engine.Options:
        out = self.out_dir if self.out_mode.value() == "custom" else ""
        s = self.settings
        s.setValue("quality", self.quality.value())
        s.setValue("scale", self.scale.value())
        s.setValue("bitrate", self.bitrate.value())
        s.setValue("vquality", self.vquality.value())
        s.setValue("vres", self.vres.currentData())
        s.setValue("dpi", self.dpi.value())
        s.setValue("merge", "true" if self.merge.isChecked() else "false")
        s.setValue("out_mode", self.out_mode.value())
        s.setValue("out_dir", self.out_dir)
        return engine.Options(
            image_quality=self.quality.value(),
            image_scale=self.scale.value(),
            audio_bitrate=self.bitrate.value(),
            video_quality=self.vquality.value(),
            video_max_height=self.vres.currentData(),
            pdf_dpi=self.dpi.value(),
            merge_pdf=self.merge.isChecked(),
            output_dir=out,
        )

    def start(self):
        if self.running:
            return
        todo = [r for r in self.rows if r.state != "done"]
        if not todo:
            return
        self.opts = opts = self._collect_options()
        merge_rows = [r for r in todo if opts.merge_pdf and r.target == "pdf"
                      and r.category in ("image", "pdf", "document")]
        if len(merge_rows) < 2:
            merge_rows = []
        jobs = [(r, r.path, r.target) for r in todo if r not in merge_rows]
        self.active = todo
        self.progress_map = {id(r): 0.0 for r in todo}
        self.results: list[Path] = []
        self.errors: list[tuple[FileRow, str]] = []
        self.t0 = time.time()
        for r in todo:
            r.set_state("queued")
        self.running = True
        self.go.hide()
        self.cancel_btn.show()
        self.cancel_btn.setEnabled(True)
        self.status.setText(f"Konvertiere {len(todo)} Datei(en)…")
        self.total_progress.setValue(0)
        threading.Thread(target=self._worker, args=(jobs, merge_rows, opts), daemon=True).start()

    def _worker(self, jobs, merge_rows, opts: engine.Options):
        b = self.bridge
        heavy = ThreadPoolExecutor(max_workers=2)
        light = ThreadPoolExecutor(max_workers=4)

        def one(row, src, target):
            if opts.cancel.is_set():
                b.failed.emit(row, "__cancel__")
                return
            b.started.emit(row)
            last = [-1.0]

            def prog(f):
                if f - last[0] >= 0.01 or f >= 1.0:
                    last[0] = f
                    b.progress.emit(row, f)
            try:
                res = engine.convert(src, target, opts, prog)
                b.done.emit(row, res)
            except engine.ConversionCancelled:
                b.failed.emit(row, "__cancel__")
            except Exception as e:  # noqa: BLE001
                b.failed.emit(row, str(e) or e.__class__.__name__)

        def merged():
            for r in merge_rows:
                b.started.emit(r)
            try:
                def prog(f):
                    for r in merge_rows:
                        b.progress.emit(r, f)
                res = engine.merge_to_pdf([r.path for r in merge_rows], opts, prog)
                for r in merge_rows:
                    b.done.emit(r, res)
            except engine.ConversionCancelled:
                for r in merge_rows:
                    b.failed.emit(r, "__cancel__")
            except Exception as e:  # noqa: BLE001
                for r in merge_rows:
                    b.failed.emit(r, str(e))

        futures = []
        if merge_rows:
            futures.append(light.submit(merged))
        for row, src, target in jobs:
            heavy_job = row.category in ("video", "audio") or target in ("mp4", "webm")
            futures.append((heavy if heavy_job else light).submit(one, row, src, target))
        wait(futures)
        heavy.shutdown()
        light.shutdown()
        b.finished.emit()

    def _update_total(self):
        if not self.active:
            return
        total = sum(self.progress_map.values()) / len(self.active)
        self.total_progress.setValue(int(total * 1000))

    def _on_started(self, row: FileRow):
        if row in self.rows:
            row.set_state("running")

    def _on_progress(self, row: FileRow, f: float):
        if row in self.rows and row.state == "running":
            row.set_progress(f)
            self.progress_map[id(row)] = f
            self._update_total()

    def _on_done(self, row: FileRow, result):
        if row not in self.rows:
            return
        row.result = Path(result)
        row.set_state("done")
        self.progress_map[id(row)] = 1.0
        if row.result not in self.results:
            self.results.append(row.result)
        self._update_total()
        finished = sum(1 for r in self.active if r.state in ("done", "error", "cancelled"))
        self.status.setText(f"{finished} von {len(self.active)} erledigt…")

    def _on_failed(self, row: FileRow, msg: str):
        if row not in self.rows:
            return
        if msg == "__cancel__":
            row.set_state("cancelled")
        else:
            row.set_state("error", msg)
            self.errors.append((row, msg))
        self.progress_map[id(row)] = 1.0
        self._update_total()

    def _on_finished(self):
        self.running = False
        self.cancel_btn.hide()
        self.go.show()
        self.total_progress.setValue(1000)
        dt = time.time() - self.t0
        ok = sum(1 for r in self.active if r.state == "done")
        cancelled = self.opts.cancel.is_set()
        self._refresh()
        QApplication.alert(self)
        if cancelled:
            self.status.setText(f"Abgebrochen. {ok} Datei(en) wurden fertig.")
            self.toast.show_toast("Konvertierung abgebrochen.", "error")
            return
        if self.errors:
            first_row, first = self.errors[0]
            self.status.setText(f"{ok} fertig, {len(self.errors)} mit Fehler (Maus über „Fehler“ zeigt den Grund).")
            self.toast.show_toast(f"{len(self.errors)} Fehler bei {first_row.path.name}: {first[:140]}", "error",
                                  self._open_output if ok else None)
        else:
            self.status.setText(f"Fertig! {ok} Datei(en) in {dt:.1f} s konvertiert.")
            self.toast.show_toast(f"{ok} Datei{'en' if ok != 1 else ''} konvertiert.", "ok", self._open_output)

    def _open_output(self):
        if self.opts and self.opts.output_dir:
            engine.reveal_in_explorer(Path(self.opts.output_dir))
        elif self.results:
            engine.reveal_in_explorer(self.results[-1])

    def cancel(self):
        if self.running and self.opts:
            self.opts.cancel.set()
            self.cancel_btn.setEnabled(False)
            self.status.setText("Breche ab…")

    # ------------------------------------------------------------ Drag & Drop

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and not self.running:
            e.acceptProposedAction()
            self.dropzone.set_active(True)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.dropzone.set_active(False)

    def dropEvent(self, e):
        self.dropzone.set_active(False)
        paths = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            e.acceptProposedAction()
            self.add_paths(paths)

    # ------------------------------------------------------------ Fenster

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.toast.reposition()

    def showEvent(self, e):
        super().showEvent(e)
        if sys.platform == "win32":
            try:
                hwnd = int(self.winId())
                val = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
                color = ctypes.c_int(0x001A1717)  # COLORREF BGR = #17171a
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), ctypes.sizeof(color))
            except Exception:
                pass

    def closeEvent(self, e):
        if self.running and self.opts:
            self.opts.cancel.set()
        super().closeEvent(e)


def main(argv: list[str] | None = None):
    argv = sys.argv if argv is None else argv
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Konverto.App")
        except Exception:
            pass
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.stylesheet())
    app.setWindowIcon(app_icon())
    win = MainWindow()
    win.show()
    files = [Path(a) for a in argv[1:] if Path(a).exists()]
    if files:
        QTimer.singleShot(0, lambda: win.add_paths(files))
    return app.exec()
