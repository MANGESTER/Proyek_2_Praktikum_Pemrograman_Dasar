# Praktikum Pemrograman Dasar - Proyek 2 (File Persistence)

# Sistem Pengelolaan Peminjaman Peralatan Laboratorium

Aplikasi CLI berbasis Python (OOP, tanpa database) untuk mengelola mahasiswa, alat, peminjaman,
dan pengembalian alat laboratorium. Selama program berjalan data berada di `list`/`dict`/`set`, dan
**disimpan permanen ke file `.csv`** di folder `data/` sehingga tetap ada saat program dibuka lagi (Proyek 2).

## Anggota Kelompok
| Nama | Peran utama |
|---|---|
| Dika | Model (`models/`), UML final |
| Abyan | `TransaksiService`, pengujian skenario peminjaman/pengembalian |
| Ayun | `MahasiswaService`, `AlatService`, Tantangan A & C |
| Adibah | `MenuCLI`, `main.py`, `LogService`, `StatistikService`, dokumentasi |

## Deskripsi Sistem
Mengatasi masalah pencatatan manual: ketersediaan alat, riwayat peminjaman, keterlambatan, dan kondisi alat setelah dikembalikan.
Aturan bisnis yang diterapkan:
1. Alat yang tidak tersedia tidak bisa dipinjam (transaksi ditolak seluruhnya / atomic).
2. Maks. 2 transaksi aktif per mahasiswa.
3. Satu transaksi dapat berisi banyak alat (`dict`), lama pinjam 1-7 hari.
4. Pengembalian sebagian diperbolehkan; transaksi `selesai` hanya bila semua alat kembali.
5. Hanya alat berkondisi **baik** yang kembali tersedia; rusak ringan/berat tidak.
6. Mahasiswa/alat yang masih ada di transaksi aktif tidak dapat dihapus.

Tantangan yang dikerjakan: **A** pencarian fleksibel, **B** statistik, **C** pemeliharaan, **D** log aktivitas.

## Struktur Program
```
lab_peminjaman/
├── main.py                  # titik masuk (memuat data .csv lalu menjalankan menu)
├── data/                    # file data .csv (dibuat otomatis, tidak di-commit)
├── data_contoh.py           # data contoh (menu 16)
├── models/                  # Mahasiswa, Alat, Transaksi, DetailPinjam, exceptions
├── services/                # MahasiswaService, AlatService, TransaksiService, LogService, StatistikService,
│                            # PenyimpananCsv (baca/tulis file .csv)
├── ui/menu.py               # MenuCLI (hanya input/output)
├── utils/validasi.py
├── tests/                   # test_skenario.py (skenario 1-6 + tantangan), test_penyimpanan.py (file .csv)
└── docs/                    # UML, keputusan desain, pengujian, code review, refleksi, pembagian tugas
```

## Cara Menjalankan
Butuh Python 3.8+ (tanpa library tambahan).
```bash
python main.py                    # jalankan aplikasi (menu 16 = muat data contoh)
                                  # data otomatis tersimpan ke folder data/ dan dimuat lagi saat dibuka
python -m unittest discover -v    # jalankan seluruh pengujian
```

## Penyimpanan File CSV
Data tersimpan otomatis setelah setiap aksi yang berhasil dan saat keluar (menu 0). File CSV (pemisah `,`, bisa dibuka
di Excel) ada di folder `data/`:
`mahasiswa.csv`, `alat.csv`, `kategori.csv`, `transaksi.csv`, `detail_transaksi.csv`, `log.csv`.
Untuk memulai dari data kosong, tutup program lalu hapus folder `data/`.
Format lengkap, alasan desain, dan keterbatasan: [`docs/penyimpanan_csv.md`](docs/penyimpanan_csv.md);
contoh isi file: [`docs/contoh_data/`](docs/contoh_data/).

## Pembagian Kontribusi
Lihat [`docs/pembagian_tugas.md`](docs/pembagian_tugas.md). Setiap anggota commit memakai akun GitHub masing-masing.

## Dokumentasi
`docs/penyimpanan_csv.md` · `docs/contoh_data/` · `docs/UML_Final/` · `docs/uml_anggota/`
