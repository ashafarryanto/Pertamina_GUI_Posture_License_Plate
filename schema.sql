-- ============================================================
-- Skema database MySQL untuk aplikasi Monitoring Plat & Postur
-- ============================================================
-- Cara pakai:
--   1. Buka terminal / MySQL Workbench, lalu jalankan file ini:
--        mysql -u root -p < schema.sql
--      (atau copy-paste isinya ke phpMyAdmin/MySQL Workbench lalu klik Execute/Go)
--   2. Sesuaikan DB_HOST/DB_USER/DB_PASSWORD di widgets/db_client.py
--      (dan web/db.php) kalau setting MySQL Anda beda dari default
--      (user root tanpa password, di localhost).
--
-- PENTING: karena foto disimpan LANGSUNG sebagai LONGBLOB (bukan cuma
-- path), kalau nanti upload gagal dengan error "packet too large" /
-- "MySQL server has gone away", naikkan setting max_allowed_packet di
-- MySQL (lihat catatan lengkap di widgets/db_client.py).
--
-- Struktur data:
--   1 baris di tabel `verifikasi`  = 1 kali proses verifikasi plat
--                                     (1 kendaraan masuk, 1 kunjungan)
--   1 baris di tabel `tags`        = 1 foto tag yang tertangkap untuk
--                                     verifikasi tsb (relasi 1-ke-banyak)
--
-- Ada 2 timestamp berbeda yang sengaja dipisah di tabel `verifikasi`:
--   captured_at -> waktu FOTO PLAT diambil (halaman Verifikasi, tombol
--                  "Verifikasi" ditekan pertama kali)
--   verified_at -> waktu data ini benar-benar DIUPLOAD/final (halaman
--                  Monitoring, tombol "Verifikasi" di situ ditekan)
-- Keduanya bisa beda beberapa menit kalau operator sempat urus tag
-- dulu sebelum upload.
--
-- Contoh: plat "B 1234 ABC" diverifikasi lalu terdeteksi 3 tag
--         -> 1 baris baru di `verifikasi`
--         -> 3 baris baru di `tags`, ketiganya verifikasi_id-nya sama
--            (menunjuk ke baris `verifikasi` di atas)
-- ============================================================

CREATE DATABASE IF NOT EXISTS pertamina_monitoring
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE pertamina_monitoring;

-- ------------------------------------------------------------
-- Tabel utama: 1 baris = 1 kali verifikasi plat
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS verifikasi (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    plate_number       VARCHAR(20)  NOT NULL,   -- mis. "B 1234 ABC"
    plate_image        LONGBLOB     NULL,       -- ISI gambar foto plat (bukan path)
    captured_at        DATETIME     NULL,       -- waktu FOTO PLAT diambil
    verified_at        DATETIME     NOT NULL,   -- waktu diupload/diverifikasi FINAL
    created_at         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Tabel anak: 1 baris = 1 foto tag, terhubung ke 1 baris verifikasi
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tags (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    verifikasi_id      INT NOT NULL,
    tag_num            INT NOT NULL,            -- nomor urut tag (1, 2, 3, ...)
    captured_time      VARCHAR(20)  NULL,       -- TANGGAL + jam tag terpasang, mis. "2026-09-09 10:35:12"
    duration           VARCHAR(20)  NULL,       -- lama proses, mis. "6.2s"
    tag_image          LONGBLOB     NULL,       -- ISI gambar foto tag (bukan path)
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (verifikasi_id) REFERENCES verifikasi(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Index supaya pencarian per plat / per verifikasi lebih cepat
CREATE INDEX idx_verifikasi_plate ON verifikasi (plate_number);
CREATE INDEX idx_tags_verifikasi  ON tags (verifikasi_id);