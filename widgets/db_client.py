"""
db_client.py

Kirim hasil verifikasi plat + semua foto tag yang tertangkap ke backend
penyimpanan -- dipanggil dari main.py setiap kali tombol "Verifikasi" di
halaman Monitoring diklik.

MENDUKUNG 4 BACKEND (atur di widgets/db_config.py, TIDAK perlu ubah
file ini sama sekali kalau pindah backend):
    - REST API              (backend tim lain, mis. .NET) -> library: requests
    - MySQL / MariaDB       (mis. XAMPP)   -> driver: pymysql
    - Microsoft SQL Server  (on-premise)   -> driver: pyodbc
    - Azure SQL Database    (cloud)        -> driver: pyodbc

SETUP AWAL:
    1. Tentukan DB_BACKEND di widgets/db_config.py.
    2. Install library/driver yang sesuai:
           REST API:   pip install requests
           MySQL:      pip install pymysql
           SQL Server / Azure SQL:  pip install pyodbc
                        (+ install "ODBC Driver 17/18 for SQL Server"
                        dari Microsoft -- ini driver sistem, bukan pip)
    3. Khusus mysql/sqlserver/azure_sql -- buat database & tabelnya:
           MySQL:      jalankan db/schema.sql
           SQL Server / Azure SQL:  jalankan db/schema_sqlserver.sql
       (REST API tidak perlu ini -- database dikelola oleh tim backend)
    4. Isi kredensial/URL di widgets/db_config.py.

CATATAN UKURAN DATA (khusus mysql/sqlserver/azure_sql, gambar disimpan
LANGSUNG bukan path): kalau upload gagal dengan error semacam
"packet too large" / "MySQL server has gone away" atau timeout, biasanya
soal batas ukuran paket di server -- lihat catatan di db/schema.sql &
db_config.py. Untuk REST API, batas ukurannya diatur oleh tim backend
(saat ini: JPEG saja, maksimal 3MB per gambar).
"""
import json
import os
from datetime import datetime

from widgets.db_config import (
    DB_BACKEND, MYSQL_CONFIG, SQLSERVER_CONFIG, AZURE_SQL_CONFIG, REST_API_CONFIG,
)

try:
    import cv2
except ImportError:
    cv2 = None  # ditangani di _bake_overlay_and_encode() -- lihat di bawah


# ============================================================
# LAPIS KONEKSI -- beda per backend, tapi semuanya menghasilkan
# fungsi get_connection() yang dipakai sama oleh upload_records()
# di bawah, jadi kode upload_records() TIDAK perlu tahu bedanya.
# ============================================================

def get_connection():
    """Buka 1 koneksi baru ke database sesuai DB_BACKEND yang aktif.
    Raise exception kalau gagal (driver belum terinstall, server tidak
    bisa dihubungi, password salah, dsb)."""
    if DB_BACKEND == "mysql":
        return _connect_mysql()
    elif DB_BACKEND in ("sqlserver", "azure_sql"):
        return _connect_sqlserver_family()
    else:
        raise ValueError(
            f"DB_BACKEND '{DB_BACKEND}' tidak dikenal. "
            f"Isi 'mysql', 'sqlserver', atau 'azure_sql' di widgets/db_config.py"
        )


def _connect_mysql():
    try:
        import pymysql
    except ImportError:
        raise RuntimeError("Modul 'pymysql' belum terinstall. Jalankan: pip install pymysql")

    cfg = MYSQL_CONFIG
    return pymysql.connect(
        host=cfg["host"], port=cfg["port"], user=cfg["user"],
        password=cfg["password"], database=cfg["database"],
        charset="utf8mb4", autocommit=False,
    )


def _connect_sqlserver_family():
    try:
        import pyodbc
    except ImportError:
        raise RuntimeError(
            "Modul 'pyodbc' belum terinstall. Jalankan: pip install pyodbc\n"
            "(dan pastikan 'ODBC Driver 17/18 for SQL Server' dari Microsoft sudah terinstall)"
        )

    cfg = SQLSERVER_CONFIG if DB_BACKEND == "sqlserver" else AZURE_SQL_CONFIG
    encrypt = "yes" if cfg.get("encrypt") else "no"

    # Named instance (mis. "localhost\SQLEXPRESS") tidak dipasangkan
    # dengan port eksplisit -- SQL Server Browser service yang cari
    # portnya otomatis. Kalau host-nya bukan named instance (tidak ada
    # "\"), baru pakai format host,port seperti biasa.
    server_part = cfg["host"] if "\\" in cfg["host"] else f"{cfg['host']},{cfg['port']}"

    conn_str = (
        f"DRIVER={cfg['driver']};"
        f"SERVER={server_part};"
        f"DATABASE={cfg['database']};"
        f"Encrypt={encrypt};TrustServerCertificate=yes;"
    )

    if cfg.get("trusted_connection"):
        # Windows Authentication -- pakai akun Windows yang sedang login,
        # tidak perlu UID/PWD. Ini yang aktif default setelah install baru.
        conn_str += "Trusted_Connection=yes;"
    else:
        conn_str += f"UID={cfg['user']};PWD={cfg['password']};"

    conn = pyodbc.connect(conn_str, autocommit=False)
    return conn


def _placeholder():
    """pymysql pakai %s, pyodbc (SQL Server) pakai ? -- helper ini
    supaya query di bawah tidak perlu ditulis dua kali per backend."""
    return "%s" if DB_BACKEND == "mysql" else "?"


def _now_expr():
    """Fungsi SQL untuk 'waktu sekarang', beda nama per backend."""
    return "NOW()" if DB_BACKEND == "mysql" else "GETDATE()"


def _insert_id_suffix():
    """
    Untuk MySQL, ID baris baru diambil lewat cursor.lastrowid (terpisah).
    Untuk SQL Server/Azure SQL, SCOPE_IDENTITY() HARUS digabung dalam
    BATCH YANG SAMA dengan perintah INSERT-nya (dipisah titik koma) --
    kalau dipanggil di cur.execute() terpisah, hasilnya selalu NULL
    karena dianggap "scope" baru yang beda dari INSERT-nya.
    """
    return "" if DB_BACKEND == "mysql" else "; SELECT SCOPE_IDENTITY();"


# ============================================================
# HELPER GAMBAR (sama untuk semua backend)
# ============================================================

def _read_image_bytes(path):
    """Baca 1 file gambar dari disk jadi bytes. Return None kalau path
    kosong/file tidak ada -- baris tetap disimpan (kolom gambar NULL),
    tidak menggagalkan seluruh upload."""
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


def _bake_overlay_and_encode(path, lines: list, max_dimension=None, jpeg_quality=90):
    """
    Baca 1 file gambar dari disk, "cap" teks info (Plat/Tag/Waktu/Durasi)
    PERMANEN ke pikselnya pakai data FINAL (nilai plat terkoreksi
    terakhir, dsb -- ini dipanggil pas upload, setelah semua koreksi
    selesai), lalu kembalikan sebagai bytes JPEG.

    max_dimension : kalau diisi (mis. 1280), gambar di-resize dulu supaya
                    sisi terpanjangnya tidak lebih dari itu -- mengurangi
                    ukuran file signifikan tanpa gambar jadi terlalu kecil
                    buat dibaca. None = tidak di-resize (ukuran asli).
    jpeg_quality   : 0-100, makin kecil makin terkompresi/makin kecil filenya.

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

    if max_dimension:
        h, w = img.shape[:2]
        longest = max(h, w)
        if longest > max_dimension:
            scale = max_dimension / longest
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    box_h = 20 + 26 * len(lines)
    overlay = img.copy()
    cv2.rectangle(overlay, (10, 10), (370, box_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)
    y = 32
    for line in lines:
        cv2.putText(img, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                    (0, 255, 255), 2, cv2.LINE_AA)
        y += 26

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if not ok:
        print(f"[WARN] Gagal encode gambar '{path}', upload tanpa overlay.")
        return _read_image_bytes(path)
    return buf.tobytes()


# ============================================================
# BACKEND: REST API (kirim ke backend tim lain, mis. .NET)
# ============================================================

def _upload_via_rest_api(plate_number, plate_image_path, plate_captured_at, tag_records: list) -> bool:
    """
    Kirim data lewat multipart/form-data ke endpoint upload, SESUAI
    kontrak yang dikasih tim backend (POST /api/VehicleInspections/upload).

    Field yang dikirim:
        LicensePlate        : teks nomor plat
        CapturedAt           : ISO datetime waktu foto plat diambil
        PlateImage           : file JPEG foto plat (WAJIB oleh API ini)
        TagsJson              : JSON array metadata semua tag
        TagImages             : file JPEG, berulang, HANYA utk tag yang punya foto
        TagImageNumbersJson  : JSON array nomor tag yang cocok urutan TagImages
    """
    try:
        import requests
    except ImportError:
        print("[ERROR] Modul 'requests' belum terinstall. Jalankan: pip install requests")
        return False

    if not plate_image_path or not os.path.exists(plate_image_path):
        print(
            f"[ERROR] Foto plat tidak ditemukan ('{plate_image_path}') -- "
            f"endpoint ini WAJIB menyertakan PlateImage, upload dibatalkan."
        )
        return False

    captured_at_str = (
        plate_captured_at.isoformat() if plate_captured_at else datetime.now().isoformat()
    )
    # versi "enak dibaca manusia" khusus buat teks yang di-cap ke gambar
    # (beda dari captured_at_str yang format ISO, buat field API)
    captured_at_display = (
        plate_captured_at.strftime("%Y-%m-%d %H:%M:%S") if plate_captured_at
        else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # susun TagsJson + daftar tag mana saja yang punya foto valid untuk di-upload
    tags_payload = []
    tag_images_to_send = []  # list of (tag_num, filepath, duration, time_display)
    for r in tag_records:
        raw_time = r.get("time") or ""
        # format tersimpan di aplikasi: "YYYY-MM-DD HH:MM:SS" (spasi) --
        # API minta ISO 8601 (huruf "T" sebagai pemisah tanggal/jam).
        captured_time_iso = raw_time.replace(" ", "T", 1) if raw_time else None

        tags_payload.append({
            "tagNumber": r.get("tag_num"),
            "capturedTime": captured_time_iso,
            "duration": r.get("duration", ""),
        })

        fp = r.get("filepath")
        if fp and os.path.exists(fp):
            tag_images_to_send.append((r.get("tag_num"), fp, r.get("duration", "-"), raw_time or "-"))
        else:
            print(f"[WARN] Foto tag #{r.get('tag_num')} tidak ditemukan, dikirim tanpa gambar (NULL).")

    data = {
        "LicensePlate": plate_number or "TANPA_PLAT",
        "CapturedAt": captured_at_str,
        "TagsJson": json.dumps(tags_payload),
    }
    if tag_images_to_send:
        data["TagImageNumbersJson"] = json.dumps([t[0] for t in tag_images_to_send])

    try:
        # foto plat -- di-cap "Plat: ..." & "Waktu: ..." di pojok kiri atas,
        # SAMA seperti yang tampil di dialog preview aplikasi (lihat
        # widgets/page_monitoring.py -- draw_overlay_lines_on_pixmap).
        plate_image_bytes = _bake_overlay_and_encode(
            plate_image_path,
            [f"Plat: {plate_number or 'TANPA_PLAT'}", f"Waktu: {captured_at_display}"],
            max_dimension=REST_API_CONFIG.get("image_max_dimension"),
            jpeg_quality=REST_API_CONFIG.get("image_quality", 80),
        )
        if plate_image_bytes is None:
            print(f"[ERROR] Gagal membaca/encode foto plat '{plate_image_path}', upload dibatalkan.")
            return False

        files = [("PlateImage", (os.path.basename(plate_image_path), plate_image_bytes, "image/jpeg"))]

        for tag_num, fp, duration, time_display in tag_images_to_send:
            tag_image_bytes = _bake_overlay_and_encode(
                fp,
                [
                    f"Plat: {plate_number or 'TANPA_PLAT'}",
                    f"Tag: #{tag_num}",
                    f"Waktu: {time_display}",
                    f"Durasi: {duration}",
                ],
                max_dimension=REST_API_CONFIG.get("image_max_dimension"),
                jpeg_quality=REST_API_CONFIG.get("image_quality", 80),
            )
            if tag_image_bytes is not None:
                files.append(("TagImages", (os.path.basename(fp), tag_image_bytes, "image/jpeg")))

        resp = requests.post(
            REST_API_CONFIG["upload_url"],
            data=data,
            files=files,
            timeout=REST_API_CONFIG.get("timeout", 30),
        )

        if resp.status_code in (200, 201):
            print(f"[UPLOAD] Berhasil! backend=rest_api, response={resp.text}")
            return True

        print(f"[ERROR] Upload API gagal -- status={resp.status_code}, body={resp.text}")
        return False

    except Exception as e:
        print(f"[ERROR] Upload ke REST API gagal: {e}")
        return False


# ============================================================
# FUNGSI UTAMA -- dipanggil dari main.py, SAMA untuk semua backend
# ============================================================

def upload_records(plate_number: str, plate_image_path, plate_captured_at, tag_records: list) -> bool:
    """
    Simpan 1 kali verifikasi plat + semua tag yang tertangkap, lewat
    backend yang aktif (REST API / MySQL / SQL Server / Azure SQL,
    tergantung DB_BACKEND di db_config.py).

    plate_number      : nomor plat yang diverifikasi, mis. "B 1234 ABC"
    plate_image_path  : path file foto plat di disk -- boleh None.
    plate_captured_at : datetime.datetime waktu foto plat diambil -- boleh None.
    tag_records        : list of dict, tiap dict berisi minimal:
                          {"tag_num", "time", "duration", "plate", "filepath"}

    Return True kalau BENAR-BENAR tersimpan, False kalau gagal (library/
    driver belum terinstall, server/API tidak bisa dihubungi, dll). Kalau
    False, UI (main.py) TIDAK menghapus daftar tag, supaya data aman &
    bisa dicoba lagi.
    """
    if not tag_records:
        print("[UPLOAD] Tidak ada tag untuk diupload, dibatalkan.")
        return False

    if DB_BACKEND == "rest_api":
        return _upload_via_rest_api(plate_number, plate_image_path, plate_captured_at, tag_records)

    ph = _placeholder()
    conn = None
    try:
        plate_image_bytes = _bake_overlay_and_encode(
            plate_image_path, [f"Plat: {plate_number or 'TANPA_PLAT'}"]
        )

        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            f"""
            INSERT INTO verifikasi (plate_number, plate_image, captured_at, verified_at)
            VALUES ({ph}, {ph}, {ph}, {_now_expr()}){_insert_id_suffix()}
            """,
            (plate_number or "TANPA_PLAT", plate_image_bytes, plate_captured_at),
        )
        if DB_BACKEND == "mysql":
            verifikasi_id = cur.lastrowid
        else:
            # pyodbc menganggap hasil dari INSERT (tidak ada baris) dan
            # SELECT SCOPE_IDENTITY() (1 baris) sebagai 2 "result set"
            # terpisah -- nextset() WAJIB dipanggil dulu untuk pindah
            # ke result set kedua (punya SELECT-nya), baru fetchone()
            # bisa diambil. Tanpa ini, muncul error
            # "No results. Previous SQL was not a query."
            cur.nextset()
            row = cur.fetchone()
            if row is None or row[0] is None:
                raise RuntimeError(
                    "SCOPE_IDENTITY() mengembalikan NULL -- INSERT ke tabel "
                    "verifikasi kemungkinan gagal/di-rollback trigger."
                )
            verifikasi_id = int(row[0])

        for r in tag_records:
            tag_lines = [
                f"Plat: {r.get('plate', plate_number or 'TANPA_PLAT')}",
                f"Tag: #{r.get('tag_num', '-')}",
                f"Waktu: {r.get('time', '-')}",
                f"Durasi: {r.get('duration', '-')}",
            ]
            tag_image_bytes = _bake_overlay_and_encode(r.get("filepath"), tag_lines)
            cur.execute(
                f"""
                INSERT INTO tags (verifikasi_id, tag_num, captured_time, duration, tag_image)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
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
            f"[UPLOAD] Berhasil! backend={DB_BACKEND}, verifikasi_id={verifikasi_id}, "
            f"plat={plate_number}, jumlah tag={len(tag_records)}"
        )
        return True

    except Exception as e:
        print(f"[ERROR] Upload ke database ({DB_BACKEND}) gagal: {e}")
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return False

    finally:
        if conn is not None:
            conn.close()