-- Jalankan ini SEKALI di phpMyAdmin (tab SQL) kalau database Anda
-- SUDAH ADA sebelumnya (sudah punya data) dan belum punya kolom
-- captured_at -- ini menambahkan kolomnya TANPA menghapus data yang
-- sudah ada.

USE pertamina_monitoring;

ALTER TABLE verifikasi ADD COLUMN captured_at DATETIME NULL AFTER plate_image;

-- Cek juga: kalau tabel tags Anda masih pakai nama kolom lama "image"
-- (bukan "tag_image"), jalankan juga baris ini:
-- ALTER TABLE tags CHANGE COLUMN image tag_image LONGBLOB NULL;