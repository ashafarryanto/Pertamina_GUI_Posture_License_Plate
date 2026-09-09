"""
Halaman 'Monitoring Plat & Postur' - versi REFLOW (lihat catatan di
page_verifikasi.py untuk penjelasan pendekatannya).
"""
import os
from PyQt5.QtCore import Qt, QTimer, QDateTime, QSize, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QFrame, QSizePolicy,
    QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QDialog
)

from widgets.design_tokens import (
    BackgroundPage, load_pixmap, make_icon_label, apply_shadow, render_cv_frame,
    cv_to_qpixmap,
    FONT_FAMILY, COLOR_NAVY, COLOR_NAVY_SOFT_BG, COLOR_BG,
    CCTV_HEADER_GRADIENT, CCTV_FOOTER_GRADIENT, CLOCK_PANEL_GRADIENT,
)


class ResizableImageLabel(QLabel):
    """
    QLabel yang menyimpan gambar aslinya (resolusi penuh) lalu otomatis
    re-scale mengikuti ukuran label SAAT INI setiap kali di-resize --
    dipakai di dialog preview tag supaya gambar ikut membesar/mengecil
    saat jendela preview ditarik, bukan cuma jendelanya yang berubah
    sementara gambarnya tetap diam di ukuran semula.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_pixmap = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(240, 160)

    def set_original_pixmap(self, pixmap: QPixmap):
        self._original_pixmap = pixmap
        self._rescale()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._original_pixmap is not None and not self._original_pixmap.isNull():
            self.setPixmap(self._original_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))


def draw_overlay_lines_on_pixmap(pixmap: QPixmap, lines: list) -> QPixmap:
    """
    Gambar teks info (Plat/Tag/Waktu/Durasi) di pojok kiri atas GAMBAR
    UNTUK DITAMPILKAN SAJA (bukan ditulis ke file aslinya) -- supaya
    selalu menunjukkan data TERBARU (ikut koreksi plat), tanpa risiko
    "kekunci" ke data lama seperti waktu masih di-bakar permanen ke file.
    """
    if not lines:
        return pixmap
    result = QPixmap(pixmap)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)

    line_h = 24
    box_w = 360
    box_h = 16 + line_h * len(lines)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(0, 0, 0, 160))
    painter.drawRect(10, 10, box_w, box_h)

    font = QFont(FONT_FAMILY)
    font.setPixelSize(16)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor(255, 230, 0))
    y = 10 + line_h
    for line in lines:
        painter.drawText(22, y, line)
        y += line_h
    painter.end()
    return result


def show_image_preview_dialog(parent, title, image_source, info_text=None, overlay_lines=None):
    """
    Dialog preview gambar yang bisa di-resize DAN di-fullscreen (tombol
    maximize aktif di title bar-nya, klik 2x untuk fullscreen penuh).
    Dipakai bersama oleh preview tag & preview foto plat supaya tidak
    ada kode duplikat.

    image_source  : path file gambar (str) ATAU QPixmap langsung.
    overlay_lines : list teks opsional yang digambar di pojok kiri atas
                    gambar SAAT PREVIEW SAJA (lihat draw_overlay_lines_on_pixmap).
    """
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    # QDialog secara default cuma punya tombol close di title bar --
    # baris ini yang menambahkan tombol minimize & maximize, supaya
    # jendela preview-nya bisa di-fullscreen-kan.
    dlg.setWindowFlags(
        dlg.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint
    )
    dlg.resize(900, 650)
    dlg.setMinimumSize(360, 280)
    dlg.setSizeGripEnabled(True)

    lay = QVBoxLayout(dlg)
    img_lbl = ResizableImageLabel()
    img_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    if isinstance(image_source, QPixmap):
        pix = image_source
    elif image_source and os.path.exists(str(image_source)):
        pix = QPixmap(str(image_source))
    else:
        pix = None

    if pix is not None and not pix.isNull():
        if overlay_lines:
            pix = draw_overlay_lines_on_pixmap(pix, overlay_lines)
        img_lbl.set_original_pixmap(pix)
    else:
        img_lbl.setText("Gambar tidak ditemukan.")
    lay.addWidget(img_lbl, 1)

    if info_text:
        info_lbl = QLabel(info_text)
        info_lbl.setAlignment(Qt.AlignCenter)
        info_lbl.setStyleSheet(f"font-family: '{FONT_FAMILY}'; padding: 8px;")
        lay.addWidget(info_lbl)

    dlg.exec_()


class TagRowWidget(QFrame):
    """
    Baris 1 tag di daftar. Seluruh area baris bisa diklik untuk preview
    gambar (lewat sinyal `clicked`) -- KECUALI tombol hapus di pojok
    kanan atas, yang menangani klik-nya sendiri (tidak ikut memicu
    preview) karena tombol Qt otomatis 'menyerap' event klik miliknya.
    """
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class FillListWidget(QListWidget):
    """
    QListWidget biasa: tinggi tiap baris ikut ukuran konten (fixed),
    jadi kalau panel-nya melebar/memanjang (mis. saat fullscreen),
    baris-barisnya diam di ukuran kecil dan sisa ruang jadi kosong.

    Kelas ini menghitung ulang tinggi tiap baris setiap kali list
    di-resize, supaya baris-baris ikut memenuhi tinggi panel yang
    tersedia -- dan ikon/font di dalam tiap baris ikut diperbesar
    proporsional juga (bukan cuma baris kosongnya yang melebar),
    supaya tidak terlihat "kosong di tengah" saat baris jadi tinggi.
    Kalau baris lebih banyak dari yang muat di tinggi minimum,
    otomatis balik jadi scrollable seperti biasa.
    """
    MIN_ROW_HEIGHT = 68
    MAX_ROW_HEIGHT = 130  # batas atas -- supaya kalau tag cuma 1-2, baris tidak
                           # "memakan" seluruh tinggi panel (kelihatan nge-tengah)

    # ukuran dasar (dipakai saat row_h == MIN_ROW_HEIGHT, scale = 1.0)
    BASE_ICON = 48
    BASE_NAME_FONT = 13
    BASE_DATE_FONT = 10
    BASE_DURATION_FONT = 12
    BASE_CLOCK_ICON = 14
    MAX_SCALE = 2.6  # batas atas supaya font tidak jadi raksasa tak wajar

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout_rows()

    def _relayout_rows(self):
        count = self.count()
        if count == 0:
            return
        available = self.viewport().height()
        row_h = max(self.MIN_ROW_HEIGHT, min(self.MAX_ROW_HEIGHT, available // count))
        scale = min(self.MAX_SCALE, row_h / self.MIN_ROW_HEIGHT)
        row_w = self.viewport().width()

        for i in range(count):
            item = self.item(i)
            row = self.itemWidget(item)
            if row is None:
                continue
            row.setFixedHeight(row_h)
            item.setSizeHint(QSize(row_w, row_h))
            self._scale_row_contents(row, scale)

    def _scale_row_contents(self, row: QWidget, scale: float):
        icon_size = int(self.BASE_ICON * scale)
        row.icon_lbl.setFixedSize(icon_size, icon_size)
        pix = row.icon_lbl.pixmap()
        if pix is not None and not pix.isNull():
            row.icon_lbl.setPixmap(
                pix.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        name_px = int(self.BASE_NAME_FONT * scale)
        date_px = int(self.BASE_DATE_FONT * scale)
        dur_px = int(self.BASE_DURATION_FONT * scale)
        clock_px = int(self.BASE_CLOCK_ICON * scale)

        row.name_lbl.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-weight: 600; font-size: {name_px}px; color: #000000;
        """)
        row.date_lbl.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-size: {date_px}px; color: #4b4b4b;
        """)
        row.duration_lbl.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-size: {dur_px}px; color: #000000;
        """)
        row.clock_icon_lbl.setFixedSize(clock_px, clock_px)


class MonitoringPage(BackgroundPage):
    def __init__(self, on_upload, on_kembali=None, on_plate_corrected=None, parent=None):
        super().__init__(parent)
        self._on_upload = on_upload
        self._on_kembali = on_kembali
        self._on_plate_corrected = on_plate_corrected
        self.tag_records = []  # list of dict -- diisi oleh add_tag(), dibaca saat upload

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(18)

        outer.addLayout(self._build_top_row())

        content_row = QHBoxLayout()
        content_row.setSpacing(24)
        content_row.addWidget(self._build_cctv_panel(), 68)
        content_row.addLayout(self._build_right_column(), 32)
        outer.addLayout(content_row, 1)

        self._start_clock()

    # ------------------------------------------------------------------
    def _build_top_row(self):
        row = QHBoxLayout()
        row.setSpacing(20)
        row.addWidget(self._build_logo_card())

        # Judul sengaja dikosongkan sesuai permintaan -- widget-nya TETAP
        # ada (disimpan di self.title_label) supaya kapan pun mau
        # ditampilkan lagi, tinggal panggil:
        #     self.title_label.setText("Monitoring Plat & Postur")
        self.title_label = QLabel("")
        self.title_label.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-weight: 800; font-size: 26px; color: #000000;
        """)
        row.addWidget(self.title_label)
        row.addStretch(1)
        return row

    def _build_logo_card(self):
        card = QFrame()
        card.setFixedSize(280, 76)
        card.setStyleSheet("background-color: #ffffff; border-radius: 14px;")
        apply_shadow(card, blur=10, y_offset=2, alpha=60)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 6)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        pix = load_pixmap("logo_pertamina.png")
        if not pix.isNull():
            logo.setPixmap(pix.scaled(220, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("PERTAMINA\nPATRA NIAGA")
            logo.setStyleSheet(f"""
                background: transparent; font-family: '{FONT_FAMILY}';
                font-weight: 800; font-size: 14px; color: #ED1C24;
            """)
        lay.addWidget(logo)
        return card

    # ------------------------------------------------------------------
    # PANEL CCTV (kiri) -- figma: node 289:113
    # ------------------------------------------------------------------
    def _build_cctv_panel(self):
        panel = QFrame()
        panel.setStyleSheet("background-color: #ffffff; border-radius: 26px;")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        apply_shadow(panel, blur=26, y_offset=12, alpha=55)

        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(76)
        header.setStyleSheet(f"""
            background: {CCTV_HEADER_GRADIENT};
            border-top-left-radius: 26px; border-top-right-radius: 26px;
        """)
        h = QHBoxLayout(header)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(12)

        icon_cctv = make_icon_label(header, "icon_cctv.png", "📹", size=34, font_px=24)
        title_cctv = QLabel("Kamera Deteksi Postur")
        title_cctv.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-weight: 600; font-size: 21px; color: #ffffff;
        """)
        self.live_dot = QLabel()
        self.live_dot.setFixedSize(16, 16)
        self.live_dot.setStyleSheet("background-color: #22c55e; border-radius: 8px;")
        self.live_text = QLabel("LIVE")
        self.live_text.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-weight: 600; font-size: 17px; color: #ffffff;
        """)
        # indikator LIVE baru muncul begitu PostureWorker benar-benar
        # mengirim frame pertama (lihat set_live()) -- disembunyikan dulu.
        self.live_dot.hide()
        self.live_text.hide()
        h.addWidget(icon_cctv)
        h.addWidget(title_cctv)
        h.addStretch(1)
        h.addWidget(self.live_dot)
        h.addWidget(self.live_text)

        self.video_label = QLabel("Memuat kamera deteksi postur...\nMohon tunggu sebentar.")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setMinimumHeight(220)
        self.video_label.setStyleSheet(f"""
            background-color: #ffffff; color: #9aa0a6;
            font-family: '{FONT_FAMILY}'; font-size: 16px;
        """)

        footer = QFrame()
        footer.setFixedHeight(56)
        footer.setStyleSheet(f"""
            background: {CCTV_FOOTER_GRADIENT};
            border-bottom-left-radius: 26px; border-bottom-right-radius: 26px;
        """)
        # catatan: sesuai Figma, footer CCTV di halaman ini sengaja polos (tanpa teks)

        vbox.addWidget(header)
        vbox.addWidget(self.video_label, 1)
        vbox.addWidget(footer)
        return panel

    def update_frame(self, cv_frame):
        """Tampilkan 1 frame hasil PostureWorker (skeleton + status tag)."""
        render_cv_frame(self.video_label, cv_frame)

    def set_live(self, active: bool):
        """Tampilkan/sembunyikan indikator LIVE -- dipanggil dari main.py
        setiap kali PostureWorker benar-benar mengirim frame."""
        self.live_dot.setVisible(active)
        self.live_text.setVisible(active)

    # ------------------------------------------------------------------
    # KOLOM KANAN: panel jam, panel plat, daftar tag, tombol
    # ------------------------------------------------------------------
    def _build_right_column(self):
        col = QVBoxLayout()
        col.setSpacing(18)
        col.addWidget(self._build_clock_panel())
        col.addWidget(self._build_plate_panel())
        col.addWidget(self._build_tag_list_panel(), 1)
        col.addLayout(self._build_buttons_row())
        return col

    def _build_clock_panel(self):
        panel = QFrame()
        panel.setStyleSheet(f"background: {CLOCK_PANEL_GRADIENT}; border-radius: 16px;")
        apply_shadow(panel, blur=14, y_offset=8, alpha=55)

        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(24, 16, 24, 16)
        vbox.setSpacing(2)

        cap_row = QHBoxLayout()
        icon_clock = make_icon_label(panel, "icon_clock.png", "🕐", size=18, font_px=14)
        caption = QLabel("Tanggal & Waktu")
        caption.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-size: 13px; color: #ffffff;
        """)
        cap_row.addWidget(icon_clock)
        cap_row.addWidget(caption)
        cap_row.addStretch(1)
        vbox.addLayout(cap_row)

        self.clock_time_label = QLabel("00 : 00 : 00")
        self.clock_time_label.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-weight: 700; font-size: 30px; color: #ffffff;
        """)
        vbox.addWidget(self.clock_time_label)

        self.clock_date_label = QLabel("")
        self.clock_date_label.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-weight: 500; font-size: 13px; color: #ffffff;
        """)
        vbox.addWidget(self.clock_date_label)
        return panel

    def _start_clock(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _tick(self):
        now = QDateTime.currentDateTime()
        self.clock_time_label.setText(now.toString("HH : mm : ss"))
        self.clock_date_label.setText(now.toString("dddd, d MMMM yyyy"))

    def _build_plate_panel(self):
        panel = QFrame()
        panel.setStyleSheet("background-color: #ffffff; border-radius: 16px;")
        apply_shadow(panel, blur=16, y_offset=6, alpha=50)

        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(24, 18, 24, 18)
        vbox.setSpacing(12)

        label_row = QHBoxLayout()
        label = QLabel("Nomor Plat Kendaraan Terverifikasi")
        label.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-weight: 600; font-size: 15px; color: #000000;
        """)
        label_row.addWidget(label)
        label_row.addStretch(1)

        # tombol preview pakai ikon yang sama gayanya dengan tombol lain
        # di aplikasi (load_pixmap + fallback emoji), bukan emoji polos.
        preview_pix = load_pixmap("icon_tag_photo.png")
        self.btn_preview_plate = QPushButton(("  " if not preview_pix.isNull() else "🖼  ") + "Preview")
        if not preview_pix.isNull():
            self.btn_preview_plate.setIcon(QIcon(preview_pix))
            self.btn_preview_plate.setIconSize(QSize(20, 20))
        self.btn_preview_plate.setCursor(Qt.PointingHandCursor)
        self.btn_preview_plate.setToolTip("Lihat foto plat hasil capture")
        self.btn_preview_plate.setMinimumHeight(40)
        self.btn_preview_plate.setStyleSheet(f"""
            QPushButton {{
                font-family: '{FONT_FAMILY}'; font-weight: 600; font-size: 14px;
                color: {COLOR_NAVY}; background-color: {COLOR_NAVY_SOFT_BG};
                border: none; border-radius: 8px; padding: 6px 16px;
            }}
            QPushButton:hover {{ background-color: #c3d8e6; }}
            QPushButton:disabled {{ color: #9aa0a6; background-color: #eef0f2; }}
        """)
        self.btn_preview_plate.clicked.connect(self._show_plate_preview)
        self.btn_preview_plate.setEnabled(False)  # aktif begitu ada foto plat (lihat set_plate_image_path)
        label_row.addWidget(self.btn_preview_plate)
        vbox.addLayout(label_row)

        # sengaja BUKAN read-only -- operator boleh merevisi/mengoreksi
        # nilai plat di sini sebelum di-upload (mis. salah baca OCR).
        # Font diperbesar & bold + kotaknya lebih tinggi supaya lebih
        # gampang dibaca dari jarak jauh (mis. dilihat operator gate).
        self.plate_input = QLineEdit()
        self.plate_input.setAlignment(Qt.AlignCenter)
        self.plate_input.setFixedHeight(76)
        self.plate_input.setFocusPolicy(Qt.ClickFocus)
        self.plate_input.setStyleSheet(f"""
            font-family: '{FONT_FAMILY}'; font-weight: 700; font-size: 32px;
            border: 1px solid #cfd9d8; border-radius: 14px; background-color: #ffffff;
        """)
        # setiap kali operator selesai mengoreksi (Enter / pindah fokus),
        # sinkronkan nilai plat yang baru ke SEMUA tag yang sudah tercatat
        # di daftar -- supaya tidak ada data plat yang "ketinggalan" lama.
        self.plate_input.textChanged.connect(self._sync_plate_correction_to_tags)
        vbox.addWidget(self.plate_input)

        self._plate_image_path = None
        self._plate_captured_at = None
        return panel

    def set_verified_plate(self, plate_text: str):
        self.plate_input.setText(plate_text)

    def _sync_plate_correction_to_tags(self):
        """
        Dipanggil SETIAP KALI teks di kolom plat berubah (live, bukan
        tunggu kolomnya kehilangan fokus -- editingFinished ternyata
        tidak selalu terpicu tepat waktu tergantung urutan klik operator).
        Semua tag yang SUDAH tercatat di daftar ikut di-update nomor
        platnya, dan PostureWorker yang sedang jalan (kalau ada) juga
        diberi tahu lewat on_plate_corrected supaya tag BARU yang
        tertangkap setelah ini juga pakai nomor plat yang benar.
        """
        new_plate = self.plate_input.text().strip() or "TANPA_PLAT"

        changed = False
        for r in self.tag_records:
            if r.get("plate") != new_plate:
                r["plate"] = new_plate
                changed = True
        if changed:
            self._rebuild_tag_list()

        if self._on_plate_corrected:
            self._on_plate_corrected(new_plate)

    def set_plate_image_path(self, path, captured_at=None):
        """Dipanggil dari main.py setelah foto plat berhasil di-capture --
        mengaktifkan tombol Preview di atas kolom plat. captured_at
        (datetime) opsional, ditampilkan di dialog preview."""
        self._plate_image_path = path
        self._plate_captured_at = captured_at
        self.btn_preview_plate.setEnabled(bool(path and os.path.exists(path)))

    def clear_plate_image(self):
        self._plate_image_path = None
        self._plate_captured_at = None
        self.btn_preview_plate.setEnabled(False)

    def _show_plate_preview(self):
        if not self._plate_image_path:
            return
        plate = self.plate_input.text().strip() or "-"
        waktu_str = (
            self._plate_captured_at.strftime("%Y-%m-%d %H:%M:%S")
            if self._plate_captured_at else "-"
        )
        info = f"Plat: {plate}    |    Waktu capture: {waktu_str}"
        show_image_preview_dialog(
            self, "Preview Foto Plat", self._plate_image_path, info,
            overlay_lines=[f"Plat: {plate}", f"Waktu: {waktu_str}"],
        )


    def _build_tag_list_panel(self):
        panel = QFrame()
        panel.setStyleSheet("background-color: #ffffff; border-radius: 16px;")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        apply_shadow(panel, blur=16, y_offset=6, alpha=50)

        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(20, 16, 20, 16)
        vbox.setSpacing(8)

        header = QLabel("Daftar Tag Terpasang")
        header.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-weight: 600; font-size: 15px; color: #000000;
        """)
        vbox.addWidget(header)

        self.tag_list = FillListWidget()
        self.tag_list.setFrameShape(QFrame.NoFrame)
        self.tag_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tag_list.setStyleSheet("""
            QListWidget { background: transparent; border: none; }
            QListWidget::item { border-bottom: 1px solid #ececec; }
            QListWidget::item:selected { background: #eef5fb; }
        """)
        # daftar dimulai kosong -- baris ditambahkan realtime lewat add_tag()
        # tiap kali PostureWorker berhasil menangkap 1 tag terpasang.
        vbox.addWidget(self.tag_list, 1)
        return panel

    def add_tag(self, tag_data: dict):
        """
        Dipanggil dari main.py setiap kali PostureWorker mengirim sinyal
        new_tag_signal (1 tag baru selesai terpasang). tag_data berisi:
            {"tag_num", "time", "duration", "plate", "thumb" (ndarray BGR
             90x60), "filepath" (path foto tersimpan di captured_tags/)}

        CATATAN: "tag_num" bawaan dari PostureWorker itu penghitung
        GLOBAL (terus naik, tidak tahu-menahu soal tag yang sudah
        dihapus di UI). Supaya nomor yang TAMPIL selalu urut rapi 1..N
        dan otomatis mulai dari 1 lagi kalau daftarnya kosong, nomor
        tampilannya di-hitung ulang di sini berdasarkan isi daftar saat
        ini -- BUKAN dipakai mentah-mentah dari tracker.
        """
        tag_data = dict(tag_data)  # jangan ubah dict asli yang dikirim worker
        existing_nums = [r.get("tag_num", 0) for r in self.tag_records]
        tag_data["tag_num"] = (max(existing_nums) + 1) if existing_nums else 1

        self.tag_records.insert(0, tag_data)
        self._rebuild_tag_list()

    def clear_tags(self):
        """Kosongkan daftar tag di layar (dipakai saat Reset & setelah upload berhasil)."""
        self.tag_list.clear()
        self.tag_records.clear()

    def remove_tag(self, tag_data: dict):
        """
        Hapus 1 tag dari daftar (tombol 'x' di pojok kanan atas tiap baris),
        lalu nomor tag yang lebih besar dari yang dihapus digeser turun 1
        supaya tetap urut tanpa lompat. Contoh: ada tag 1,2,3,4,5 -> hapus
        tag 3 -> tag 4 jadi 3, tag 5 jadi 4 (tag 1 & 2 tidak berubah).
        """
        deleted_num = tag_data.get("tag_num")
        self.tag_records = [r for r in self.tag_records if r is not tag_data]
        if deleted_num is not None:
            for r in self.tag_records:
                if r.get("tag_num") is not None and r["tag_num"] > deleted_num:
                    r["tag_num"] -= 1
        self._rebuild_tag_list()

    def _rebuild_tag_list(self):
        """Gambar ulang seluruh daftar tag dari self.tag_records (urutan dipertahankan)."""
        self.tag_list.clear()
        for data in self.tag_records:
            row = self._build_tag_row(data)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.tag_list.addItem(item)
            self.tag_list.setItemWidget(item, row)
        self.tag_list._relayout_rows()

    def _show_tag_preview(self, tag_data: dict):
        """Tampilkan foto tag ukuran penuh saat barisnya diklik."""
        self._sync_plate_correction_to_tags()  # jaring pengaman -- pastikan datanya paling baru
        plate = tag_data.get("plate", "-")
        tag_num = tag_data.get("tag_num", "?")
        info = (
            f"Plat: {plate}    |    Tag #{tag_num}    |    "
            f"Waktu: {tag_data.get('time', '-')}    |    "
            f"Durasi: {tag_data.get('duration', '-')}"
        )
        overlay_lines = [
            f"Plat: {plate}",
            f"Tag: #{tag_num}",
            f"Waktu: {tag_data.get('time', '-')}",
            f"Durasi: {tag_data.get('duration', '-')}",
        ]
        show_image_preview_dialog(
            self, f"Preview - Plat {plate} - Tag #{tag_num}",
            tag_data.get("filepath"), info, overlay_lines,
        )

    def _build_tag_row(self, tag_data: dict) -> QWidget:
        plate = tag_data.get("plate", "-")
        tag_num = tag_data.get("tag_num", "?")
        time_str = tag_data.get("time", "-")
        duration = tag_data.get("duration", "-")
        thumb = tag_data.get("thumb")  # ndarray BGR kecil (90x60) dari PostureWorker

        row = TagRowWidget()
        row.setCursor(Qt.PointingHandCursor)
        row.setStyleSheet("background: transparent;")
        row.clicked.connect(lambda: self._show_tag_preview(tag_data))

        h = QHBoxLayout(row)
        h.setContentsMargins(4, 8, 4, 8)
        h.setSpacing(12)

        icon = QLabel(row)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(48, 48)
        icon.setStyleSheet("background-color: #f3f4f6; border-radius: 8px;")
        if thumb is not None:
            pix = cv_to_qpixmap(thumb)
            icon.setPixmap(pix.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon.setText("🖼")
            icon.setStyleSheet(icon.styleSheet() + "font-size: 22px;")

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        name_lbl = QLabel(f"Plat {plate} - Tag #{tag_num}")
        name_lbl.setWordWrap(True)
        name_lbl.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-weight: 600; font-size: 13px; color: #000000;
        """)
        date_lbl = QLabel(f"Terpasang {time_str}")
        date_lbl.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-size: 10px; color: #4b4b4b;
        """)
        text_col.addWidget(name_lbl)
        text_col.addWidget(date_lbl)

        duration_row = QHBoxLayout()
        duration_row.setSpacing(4)
        clock_icon = make_icon_label(row, "icon_clock_small.png", "🕐", size=14, font_px=12)
        duration_lbl = QLabel(duration)
        duration_lbl.setStyleSheet(f"""
            background: transparent; font-family: '{FONT_FAMILY}';
            font-size: 12px; color: #000000;
        """)
        duration_row.addWidget(clock_icon)
        duration_row.addWidget(duration_lbl)

        # tombol hapus -- pojok kanan atas baris (lihat TagRowWidget di atas
        # untuk penjelasan kenapa klik tombol ini tidak ikut memicu preview)
        delete_btn = QPushButton("✕")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setToolTip("Hapus tag ini")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #fdecea; color: #c0392b;
                border-radius: 12px; border: none; font-weight: 700;
            }
            QPushButton:hover { background-color: #f8c9c4; }
        """)
        delete_btn.clicked.connect(lambda: self.remove_tag(tag_data))

        h.addWidget(icon, alignment=Qt.AlignVCenter)
        h.addLayout(text_col, 1)
        h.addLayout(duration_row)
        h.addWidget(delete_btn, alignment=Qt.AlignTop)
        h.setAlignment(text_col, Qt.AlignVCenter)
        h.setAlignment(duration_row, Qt.AlignVCenter)

        # simpan referensi supaya FillListWidget bisa scale ulang ukuran
        # ikon & font saat baris ini melebar/memanjang (lihat _relayout_rows)
        row.icon_lbl = icon
        row.name_lbl = name_lbl
        row.date_lbl = date_lbl
        row.clock_icon_lbl = clock_icon
        row.duration_lbl = duration_lbl
        return row

    # ------------------------------------------------------------------
    def _build_buttons_row(self):
        row = QHBoxLayout()
        row.setSpacing(16)

        back_pix = load_pixmap("icon_back.png")
        self.btn_kembali = QPushButton(("  " if not back_pix.isNull() else "‹  ") + "Kembali")
        if not back_pix.isNull():
            self.btn_kembali.setIcon(QIcon(back_pix))
            self.btn_kembali.setIconSize(QSize(22, 22))
        self.btn_kembali.setMinimumHeight(54)
        self.btn_kembali.setCursor(Qt.PointingHandCursor)
        self.btn_kembali.setStyleSheet(f"""
            QPushButton {{
                font-family: '{FONT_FAMILY}'; font-weight: 600; font-size: 18px;
                color: {COLOR_NAVY}; background-color: {COLOR_NAVY_SOFT_BG};
                border: 1px solid {COLOR_NAVY}; border-radius: 8px;
            }}
            QPushButton:hover {{ background-color: #c3d8e6; }}
        """)
        if self._on_kembali:
            self.btn_kembali.clicked.connect(self._on_kembali)

        verif_pix = load_pixmap("icon_verified.png")
        self.btn_verifikasi = QPushButton(("  " if not verif_pix.isNull() else "✓  ") + "Verifikasi")
        if not verif_pix.isNull():
            self.btn_verifikasi.setIcon(QIcon(verif_pix))
            self.btn_verifikasi.setIconSize(QSize(22, 22))
        self.btn_verifikasi.setToolTip("Upload foto plat & semua tag yang tertangkap ke database")
        self.btn_verifikasi.setMinimumHeight(54)
        self.btn_verifikasi.setCursor(Qt.PointingHandCursor)
        self.btn_verifikasi.setStyleSheet(f"""
            QPushButton {{
                font-family: '{FONT_FAMILY}'; font-weight: 600; font-size: 18px;
                color: #ffffff; background-color: {COLOR_NAVY};
                border-radius: 8px; border: none;
            }}
            QPushButton:hover {{ background-color: #062338; }}
        """)
        self.btn_verifikasi.clicked.connect(self._on_upload)

        row.addWidget(self.btn_kembali, 1)
        row.addWidget(self.btn_verifikasi, 1)
        return row