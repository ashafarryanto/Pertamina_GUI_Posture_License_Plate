# Monitoring Plat & Postur — Pertamina Patra Niaga

Aplikasi desktop (PyQt5) untuk memantau kendaraan yang masuk lewat **deteksi
plat nomor otomatis (ANPR)** dan **deteksi postur + pemasangan tag
keselamatan** secara realtime, memakai YOLOv8 + OpenCV.

<p align="center">
  <img src="assets/app_icon.png" width="96" alt="App icon">
</p>

---

## ✨ Fitur

- **ANPR (Automatic Number Plate Recognition)**
  Deteksi lokasi plat nomor pakai YOLOv8 custom, dibaca teksnya pakai
  EasyOCR, dinormalisasi ke format plat Indonesia (`B 1234 ABC`), dan
  distabilkan pakai voting antar-frame supaya teks yang ditampilkan tidak
  "kedip-kedip" berubah tiap frame.

- **Deteksi Postur & Tracking Tag**
  Deteksi orang + 17 keypoint tubuh (YOLOv8-pose), klasifikasi postur
  (Berdiri / Menunduk / Jongkok) berdasarkan sudut lutut & pinggang, lalu
  melacak durasi tag keselamatan terpasang — otomatis meng-capture foto
  begitu proses pemasangan selesai.

- **UI Desktop 2 Halaman**
  - **Verifikasi** — video live kamera ANPR, auto-isi nomor plat, koreksi
    manual kalau OCR salah baca.
  - **Monitoring** — video live kamera deteksi postur, daftar tag yang
    tertangkap (bisa di-preview & dihapus dengan renumbering otomatis).

- **Responsif** — layout reflow, bisa di-resize/maximize/fullscreen bebas,
  mendukung mode kios (`--kiosk`) untuk layar kecil (mis. Jetson Nano +
  panel 7").

- **Ringan** — cuma 1 model AI yang aktif dalam satu waktu (ANPR di
  halaman Verifikasi, Deteksi Postur di halaman Monitoring), bukan
  dua-duanya sekaligus.

---

## 📁 Struktur Proyek

```
pertamina_gui/
├── main.py                     # entry point aplikasi
├── assets/                     # logo, ikon, background (hasil export Figma)
│   ├── style.qss
│   ├── app_icon.ico / .png
│   └── *.png
│
├── widgets/                    # kode UI (PyQt5)
│   ├── design_tokens.py        # warna, gradient, helper bersama
│   ├── page_verifikasi.py      # halaman "Verifikasi Plat Nomor"
│   ├── page_monitoring.py      # halaman "Monitoring Plat & Postur"
│   └── workers.py              # ANPRWorker & PostureWorker (QThread)
│
└── detection/                  # inti sistem deteksi
    ├── anpr/
    │   ├── anpr_main.py        # konfigurasi & pipeline ANPR
    │   ├── plate_utils.py      # normalisasi teks plat Indonesia
    │   ├── video_source.py     # wrapper VideoCapture (file & live-camera)
    │   └── model.pt            # (taruh sendiri, tidak ikut di repo)
    ├── pose/
    │   ├── v6.py                # konfigurasi & tracking tag/postur
    │   └── posture_detect.py    # klasifikasi postur dari keypoint
    └── model/
        └── yolov8n-pose.pt      # (taruh sendiri, tidak ikut di repo)
```

---

## 🔧 Requirements

- Python 3.9+
- PyQt5
- OpenCV (`opencv-python`)
- Ultralytics (YOLOv8)
- PyTorch
- EasyOCR
- NumPy

Instal semuanya:

```bash
pip install PyQt5 opencv-python ultralytics torch easyocr numpy
```

> Kalau punya GPU NVIDIA, install PyTorch versi CUDA-nya dulu (lihat
> [pytorch.org](https://pytorch.org)) supaya inferensi jauh lebih cepat.
> Tanpa GPU, aplikasi tetap jalan di CPU tapi lebih lambat.

---

## 🚀 Instalasi

1. **Clone repo ini**
   ```bash
   git clone <url-repo-ini>
   cd pertamina_gui
   ```

2. **Install dependency**
   ```bash
   pip install -r requirements.txt
   ```

3. **Taruh model & sumber video Anda sendiri:**
   | File | Lokasi |
   |---|---|
   | Model deteksi plat (`model.pt`) | `detection/model/model.pt` |
   | Model pose (`yolov8n-pose.pt` / `yolov8s-pose.pt` / `yolov8m-pose.pt`) | `detection/model/` |
   | Video uji ANPR (opsional, kalau belum pakai kamera asli) | `detection/anpr/` |
   | Video uji Postur (opsional) | `detection/pose/` |

4. **Sesuaikan sumber video** di dua file konfigurasi:

   `detection/anpr/anpr_main.py`
   ```python
   SOURCE = str(Path(__file__).resolve().parent / "3.mp4")   # file video uji
   # SOURCE = 0                                                # webcam
   # SOURCE = "rtsp://user:pass@192.168.1.10:554/stream1"      # kamera IP/CCTV
   ```

   `detection/pose/v6.py`
   ```python
   SOURCE = str(Path(__file__).resolve().parent / "14.mp4")  # file video uji
   # SOURCE = 0
   # SOURCE = "rtsp://user:pass@192.168.1.11:554/stream1"
   ```

---

## ▶️ Menjalankan

```bash
python main.py
```

Mode kios (fullscreen tanpa title bar, cocok untuk perangkat tertanam /
layar kecil):

```bash
python main.py --kiosk
```

Tekan `Esc` untuk keluar dari mode kios saat testing.

---

## 🧭 Alur Penggunaan

1. Aplikasi terbuka di halaman **Verifikasi** — kamera ANPR otomatis
   jalan, kolom nomor plat terisi otomatis dari hasil OCR.
2. Operator boleh mengoreksi manual kalau bacaan OCR salah, lalu tekan
   **Verifikasi** — foto plat disimpan, ANPR berhenti (hemat resource),
   dan aplikasi pindah ke halaman **Monitoring** sambil menjalankan
   deteksi postur.
3. Di halaman Monitoring, setiap tag keselamatan yang selesai terpasang
   otomatis masuk ke daftar (foto, waktu, durasi). Tag bisa di-klik untuk
   preview foto ukuran penuh, atau dihapus kalau salah tangkap.
4. Tombol **Kembali** membawa balik ke halaman Verifikasi tanpa
   menghentikan proses deteksi postur di background.
5. Tombol **Reset** menghentikan semua proses dan memulai ulang dari nol
   untuk kendaraan berikutnya.

---

## ⚙️ Parameter Penting

| Parameter | Lokasi | Fungsi |
|---|---|---|
| `CONF_THRESHOLD` | `anpr_main.py` | Ambang keyakinan deteksi plat |
| `OCR_EVERY_N_FRAME` | `anpr_main.py` | OCR dijalankan tiap N frame (biar tetap realtime) |
| `CONF_THRESHOLD_DETECT` | `v6.py` | Ambang keyakinan deteksi orang |
| `ALERT_SECONDS` | `v6.py` | Lama tag harus "diam" sebelum dianggap selesai terpasang |
| `RATIO_JONGKOK` / `RATIO_MENUNDUK` | `v6.py` | Kalibrasi rasio tinggi tubuh untuk klasifikasi postur |
| `MODEL_PATH` | `anpr_main.py` / `v6.py` | Lokasi file model `.pt` |

---

## 🖥️ Deployment ke Perangkat Tertanam (mis. Jetson Nano)

- Install PyQt5 lewat `apt` (bukan `pip`) di ARM/Jetson untuk hindari
  compile lama: `sudo apt-get install python3-pyqt5`.
- Jalankan dengan `python3 main.py --kiosk`.
- Kalau terasa lag, matikan efek shadow: set `ENABLE_SHADOWS = False` di
  `widgets/design_tokens.py`.
- Cek resolusi layar dengan `xrandr`, sesuaikan `MIN_WIDTH`/`MIN_HEIGHT`
  di `main.py` kalau perlu.

---

## 📄 Lisensi

Internal project — Pertamina Patra Niaga.
