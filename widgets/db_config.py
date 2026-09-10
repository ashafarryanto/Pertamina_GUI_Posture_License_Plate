"""
db_config.py

SATU-SATUNYA FILE yang perlu diubah kalau Anda pindah database (MySQL ->
SQL Server -> Azure SQL Database, atau sebaliknya). Kode lain
(widgets/db_client.py, main.py) tidak perlu disentuh sama sekali --
mereka cuma manggil upload_records() tanpa peduli database-nya apa.

CARA PINDAH DATABASE:
    1. Ganti nilai DB_BACKEND di bawah ini ke salah satu:
           "mysql"      -> MySQL / MariaDB (XAMPP, dsb) -- default sekarang
           "sqlserver"  -> Microsoft SQL Server lokal/on-premise
           "azure_sql"  -> Azure SQL Database (cloud)
    2. Isi konfigurasi koneksi yang sesuai di bagian bawah (host, user,
       password, dst).
    3. Install driver Python yang dibutuhkan (lihat komentar tiap
       backend di bawah).
    4. Jalankan schema SQL yang sesuai (db/schema.sql untuk MySQL,
       db/schema_sqlserver.sql untuk SQL Server/Azure SQL).
    Tidak ada kode lain yang perlu diubah.
"""

# ============================================================
# GANTI INI SAJA untuk pindah database
# ============================================================
DB_BACKEND = "sqlserver"   # "mysql" | "sqlserver" | "azure_sql"


# ------------------------------------------------------------
# 1) MySQL / MariaDB (XAMPP, dsb) -- butuh: pip install pymysql
# ------------------------------------------------------------
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "pertamina_monitoring",
}

# ------------------------------------------------------------
# 2) Microsoft SQL Server LOKAL (on-premise / server kantor sendiri)
#    Butuh: pip install pyodbc
#    DAN install "ODBC Driver 17 (atau 18) for SQL Server" dari Microsoft
#    (bukan cuma pip install -- ini driver sistem, download terpisah).
#    host bisa berupa "localhost", "NAMA_SERVER", atau
#    "NAMA_SERVER\\NAMA_INSTANCE" (mis. "localhost\\SQLEXPRESS" -- ini
#    yang dipakai kalau Anda install pakai edisi Express, cek nama
#    instance-nya di layar akhir instalasi).
#
#    trusted_connection = True artinya pakai WINDOWS AUTHENTICATION
#    (login pakai akun Windows yang sedang aktif, TIDAK perlu isi
#    user/password) -- ini yang aktif secara default begitu SQL Server
#    baru diinstall. Set False kalau mau pakai SQL Server Authentication
#    (user/password, mis. "sa") -- itu perlu diaktifkan manual dulu di
#    SSMS (Server Properties > Security > SQL Server and Windows
#    Authentication mode), tidak aktif dari awal.
# ------------------------------------------------------------
SQLSERVER_CONFIG = {
    "host": "localhost\\SQLEXPRESS",
    "port": 1433,
    "trusted_connection": True,   # True = Windows Authentication (tidak perlu user/password)
    "user": "sa",                  # dipakai HANYA kalau trusted_connection = False
    "password": "",                # dipakai HANYA kalau trusted_connection = False
    "database": "pertamina_monitoring",
    "driver": "{ODBC Driver 17 for SQL Server}",
    "encrypt": False,  # jaringan lokal biasanya tidak wajib SSL
}

# ------------------------------------------------------------
# 3) Azure SQL Database (cloud) -- butuh: pip install pyodbc
#    DAN "ODBC Driver 17/18 for SQL Server" (sama seperti di atas).
#    host = alamat server Azure, formatnya:
#           "namaserver.database.windows.net"
#    (dapat dilihat di halaman resource SQL Database di Azure Portal)
#    Jangan lupa: di Azure Portal, tambahkan IP Address komputer Anda
#    ke "Firewall rules" server itu, kalau tidak koneksi akan ditolak.
# ------------------------------------------------------------
AZURE_SQL_CONFIG = {
    "host": "namaserver.database.windows.net",
    "port": 1433,
    "user": "youruser",
    "password": "",
    "database": "pertamina_monitoring",
    "driver": "{ODBC Driver 17 for SQL Server}",
    "encrypt": True,  # Azure SQL WAJIB pakai koneksi terenkripsi
}