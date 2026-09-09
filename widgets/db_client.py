"""
db_client.py

Koneksi ke database MySQL LOKAL untuk menyimpan hasil verifikasi plat
beserta semua foto tag yang tertangkap -- GAMBARNYA DISIMPAN LANGSUNG
di database (kolom LONGBLOB), bukan cuma path filenya. Dipanggil dari
main.py setiap kali tombol "Verifikasi" di halaman Monitoring diklik.

SETUP AWAL (WAJIB, sebelum tombol Verifikasi di halaman Monitoring bisa
berhasil upload):

    1. Install MySQL Server / XAMPP di komputer Anda (kalau belum ada).
    2. Install driver Python:
           pip install pymysql
    3. Buat database & tabelnya -- jalankan file db/schema.sql, mis:
           mysql -u root -p < db/schema.sql
       (atau copy-paste isi file itu ke phpMyAdmin/MySQL Workbench,
       klik Execute/Go)
    4. Kalau setting MySQL Anda beda dari default (user root tanpa
       password, di localhost port 3306), sesuaikan konstanta DB_* di
       bawah ini.

CATATAN PENTING soal ukuran data (karena gambar disimpan LANGSUNG,
bukan cuma path): kalau nanti muncul error semacam
"MySQL server has gone away" atau "packet too large" saat upload,
artinya foto yang dikirim lebih besar dari batas `max_allowed_packet`
di server MySQL Anda (default XAMPP biasanya cuma 1-4 MB). Cara naikkan:
    1. Cari file my.ini (XAMPP: xampp/mysql/bin/my.ini).
    2. Di bagian [mysqld], tambahkan/ubah baris:
           max_allowed_packet=64M
    3. Restart MySQL dari XAMPP Control Panel.

Struktur data (lihat db/schema.sql untuk detail lengkap):
    tabel `verifikasi` -- 1 baris = 1 kali proses verifikasi plat
                          (kolom `plate_image` = ISI foto plat, LONGBLOB)
    tabel `tags`       -- 1 baris = 1 foto tag, terhubung (1-ke-banyak)
                          ke 1 baris `verifikasi` lewat verifikasi_id
                          (kolom `tag_image` = ISI foto tag, LONGBLOB)
"""
import os

try:
    import cv2
except ImportError:
    cv2 = None  # ditangani di _bake_overlay_and_encode() -- lihat di bawah

try:
    import pymysql
except ImportError:
    pymysql = None  # ditangani di upload_records() -- lihat di bawah

# ------------------------------------------------------------------
# KONFIGURASI KONEKSI -- sesuaikan dengan setting MySQL Anda
# ------------------------------------------------------------------
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = ""                       # <-- isi password MySQL Anda di sini
DB_NAME = "pertamina_monitoring"


def get_connection():
    """Buka 1 koneksi baru ke database. Raise exception kalau gagal
    (mis. MySQL belum jalan, password salah, database belum dibuat)."""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        autocommit=False,
    )


def _read_image_bytes(path):
    """Baca 1 file gambar dari disk jadi bytes, siap di-insert ke kolom
    LONGBLOB. Return None kalau path kosong/file tidak ada -- baris tetap
    disimpan (cuma kolom gambarnya NULL), tidak menggagalkan seluruh upload."""
    if not path or not os.path.exists(path):
        if path:
            print(f"[WARN] File gambar tidak ditemukan, dilewati: {path}")
        return None
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception as e:
        print(f"[WARN] Gagal membaca file gambar '{path}': {e}")
        return None


def _bake_overlay_and_encode(path, lines: list):
    """
    Baca 1 file gambar dari disk, "cap" teks info (mis. Plat/Tag/Waktu/
    Durasi) PERMANEN ke pikselnya pakai data yang sudah FINAL (nilai
    plat terkoreksi terakhir, dsb -- karena ini dipanggil pas upload,
    setelah semua koreksi selesai), lalu kembalikan sebagai bytes JPEG
    siap disimpan ke kolom LONGBLOB.

    Ini beda dengan overlay yang muncul waktu preview di aplikasi (itu
    cuma digambar sementara, tidak permanen) -- di sini baru betul-betul
    ditulis ke gambar, karena inilah titik "final" datanya (sudah mau
    diarsipkan ke database, tidak akan dikoreksi lagi setelah ini).

    Kalau OpenCV tidak terinstall atau file gagal dibaca/di-decode,
    otomatis fallback ke file mentah tanpa overlay (upload tetap jalan).
    """
    if cv2 is None:
        return _read_image_bytes(path)
    if not path or not os.path.exists(path):
        if path:
            print(f"[WARN] File gambar tidak ditemukan, dilewati: {path}")
        return None

    img = cv2.imread(path)
    if img is None:
        print(f"[WARN] Gagal decode gambar '{path}', upload tanpa overlay.")
        return _read_image_bytes(path)

    box_h = 20 + 26 * len(lines)
    overlay = img.copy()
    cv2.rectangle(overlay, (10, 10), (370, box_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)
    y = 32
    for line in lines:
        cv2.putText(img, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                    (0, 255, 255), 2, cv2.LINE_AA)
        y += 26

    ok, buf = cv2.imencode(".jpg", img)
    if not ok:
        print(f"[WARN] Gagal encode gambar '{path}', upload tanpa overlay.")
        return _read_image_bytes(path)
    return buf.tobytes()


def upload_records(plate_number: str, plate_image_path, plate_captured_at, tag_records: list) -> bool:
    """
    Simpan 1 kali verifikasi plat + semua tag yang tertangkap ke MySQL.
    Foto plat & foto tiap tag dibaca dari disk lalu disimpan LANGSUNG
    sebagai data gambar (LONGBLOB) di database.

    plate_number      : nomor plat yang diverifikasi, mis. "B 1234 ABC"
    plate_image_path  : path file foto plat di disk (folder
                         captured_plates/), dipakai HANYA untuk dibaca
                         isinya lalu disimpan ke DB -- boleh None kalau
                         operator belum sempat verifikasi di halaman
                         Verifikasi (langsung pakai tombol "Monitoring").
    plate_captured_at : objek datetime.datetime -- waktu FOTO PLAT
                         diambil (beda dengan waktu upload/verified_at
                         yang otomatis pakai NOW() di server MySQL).
                         Boleh None kalau tidak diketahui.
    plate_image_path : path file foto plat di disk (folder
                        captured_plates/), dipakai HANYA untuk dibaca
                        isinya lalu disimpan ke DB -- boleh None kalau
                        operator belum sempat verifikasi di halaman
                        Verifikasi (langsung pakai tombol "Monitoring").
    tag_records       : list of dict, tiap dict berisi minimal:
                         {"tag_num", "time", "duration", "filepath"}
                         ("filepath" = path foto tag di disk, dibaca
                         isinya lalu disimpan ke DB)

    Return True kalau BENAR-BENAR tersimpan di database, False kalau
    gagal (driver belum terinstall, MySQL tidak bisa dihubungi, dll).
    Kalau False, UI (main.py) TIDAK akan menghapus daftar tag di layar,
    supaya datanya tidak hilang dan bisa dicoba upload lagi.
    """
    if pymysql is None:
        print("[ERROR] Modul 'pymysql' belum terinstall. Jalankan: pip install pymysql")
        return False

    if not tag_records:
        print("[UPLOAD] Tidak ada tag untuk diupload, dibatalkan.")
        return False

    conn = None
    try:
        plate_image_bytes = _bake_overlay_and_encode(
            plate_image_path, [f"Plat: {plate_number or 'TANPA_PLAT'}"]
        )

        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO verifikasi (plate_number, plate_image, captured_at, verified_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (plate_number or "TANPA_PLAT", plate_image_bytes, plate_captured_at),
            )
            verifikasi_id = cur.lastrowid

            for r in tag_records:
                tag_lines = [
                    f"Plat: {r.get('plate', plate_number or 'TANPA_PLAT')}",
                    f"Tag: #{r.get('tag_num', '-')}",
                    f"Waktu: {r.get('time', '-')}",
                    f"Durasi: {r.get('duration', '-')}",
                ]
                tag_image_bytes = _bake_overlay_and_encode(r.get("filepath"), tag_lines)
                cur.execute(
                    """
                    INSERT INTO tags (verifikasi_id, tag_num, captured_time, duration, tag_image)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        verifikasi_id,
                        r.get("tag_num"),
                        r.get("time"),
                        r.get("duration"),
                        tag_image_bytes,
                    ),
                )

        conn.commit()
        print(
            f"[UPLOAD] Berhasil! verifikasi_id={verifikasi_id}, "
            f"plat={plate_number}, jumlah tag={len(tag_records)} (gambar tersimpan di DB)"
        )
        return True

    except Exception as e:
        print(f"[ERROR] Upload ke database gagal: {e}")
        if conn is not None:
            conn.rollback()
        return False

    finally:
        if conn is not None:
            conn.close()