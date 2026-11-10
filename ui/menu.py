from datetime import date, datetime

from data_contoh import muat_data_contoh
from models.alat import Kondisi_Valid
from models.exceptions import LabError, PenyimpananError, ValidasiError
from models.transaksi import max_hari

class MenuCLI:
    """Lapisan antarmuka: hanya membaca input & mencetak. Logika ada di services."""

    def __init__(self, mahasiswa, alat, transaksi, statistik, log, penyimpanan=None):
        self.mhs, self.alat, self.trx, self.stat, self.log = mahasiswa, alat, transaksi, statistik, log
        self.penyimpanan = penyimpanan  # bila None, data tidak disimpan ke file
        self._aksi = {
            "1": self.kelola_mahasiswa, "2": self.kelola_alat, "3": self.buat_transaksi,
            "4": self.tampil_transaksi, "5": self.proses_pengembalian, "6": self.cari_transaksi,
            "7": lambda: self._cetak(self.alat.daftar_tersedia(), "Alat tersedia"),
            "8": lambda: self._cetak(self.alat.daftar_dipinjam(), "Alat sedang dipinjam"),
            "9": lambda: self._cetak(self.alat.daftar_rusak(), "Alat rusak"),
            "10": self.riwayat_mahasiswa, "11": self.cari_alat, "12": self.pemeliharaan,
            "13": self.statistik, "14": self.tampil_log, "15": self.kelola_kategori,
            "16": self.data_contoh,
        }

    def _nama_mhs(self, nim):
        try:
            return self.mhs.ambil(nim).nama
        except LabError:
            return "(sudah dihapus)"

    def _nama_alat(self, kode):
        try:
            return self.alat.ambil(kode).nama
        except LabError:
            return "(alat sudah dihapus)"

    @staticmethod
    def _tanya(label):
        return input(f"{label}: ").strip()

    @staticmethod
    def _tanya_tanggal():
        teks = input("Tanggal (YYYY-MM-DD, kosong = hari ini): ").strip()
        if not teks:
            return date.today()
        try:
            return datetime.strptime(teks, "%Y-%m-%d").date()
        except ValueError:
            raise ValidasiError("Format tanggal harus YYYY-MM-DD.")

    @staticmethod
    def _cetak(daftar, judul):
        print(f"\n== {judul} ({len(daftar)}) ==")
        if not daftar:
            print("(kosong)")
        for item in daftar:
            print(" -", item)

    def _cetak_transaksi(self, daftar, judul):
        print(f"\n== {judul} ({len(daftar)}) ==")
        if not daftar:
            print("(kosong)")
        for t in daftar:
            print(f"\n{t.id} | {t.nim} ({self._nama_mhs(t.nim)}) | pinjam {t.tanggal_pinjam} | batas {t.batas_kembali} | {t.status.upper()}")
            for kode, d in t.items.items():
                if d.sudah_kembali:
                    tl = " TERLAMBAT" if d.terlambat else ""
                    info = f"kembali {d.tanggal_kembali}, kondisi {d.kondisi_kembali}{tl}"
                else:
                    info = "masih dipinjam"
                print(f"    - {kode} {self._nama_alat(kode)}: {info}")

    def _pilih_kondisi(self):
        for i, k in enumerate(Kondisi_Valid, 1):
            print(f"  {i}. {k}")
        pilihan = self._tanya("Pilih kondisi (nomor)")
        if not pilihan.isdecimal() or not 1 <= int(pilihan) <= len(Kondisi_Valid):
            raise ValidasiError("Pilihan kondisi tidak valid.")
        return Kondisi_Valid[int(pilihan) - 1]

    def _simpan(self):
        """Tulis seluruh data ke file .csv. Kegagalan menulis hanya ditampilkan sebagai peringatan."""
        if self.penyimpanan is None:
            return
        try:
            self.penyimpanan.simpan()
        except PenyimpananError as e:
            print(f"[!] PERINGATAN: data belum tersimpan ke file. {e}")

    def jalan(self):
        while True:
            print("""
=== SISTEM PEMINJAMAN PERALATAN LABORATORIUM ===
 1. Kelola data mahasiswa        9. Tampilkan alat rusak
 2. Kelola data alat            10. Riwayat peminjaman mahasiswa
 3. Buat transaksi peminjaman   11. Cari alat (kode/nama/kategori)
 4. Tampilkan transaksi         12. Pemeliharaan alat
 5. Proses pengembalian alat    13. Statistik peminjaman
 6. Cari transaksi (mahasiswa)  14. Log aktivitas
 7. Tampilkan alat tersedia     15. Kelola kategori alat
 8. Tampilkan alat dipinjam     16. Muat data contoh
 0. Keluar""")
            pilihan = self._tanya("Pilih menu")
            if pilihan == "0":
                self._simpan()
                print("Data tersimpan. Terima kasih.")
                return
            aksi = self._aksi.get(pilihan)
            if aksi is None:
                print("[!] Menu tidak dikenal.")
                continue
            try:
                aksi()
                self._simpan()  # setiap aksi yang berhasil langsung disimpan ke file
            except LabError as e:
                print(f"[!] {e}")

    def kelola_mahasiswa(self):
        print("\n1.Tambah 2.Edit 3.Hapus 4.Cari 5.Lihat semua")
        p = self._tanya("Pilih")
        if p == "1":
            m = self.mhs.tambah(self._tanya("NIM"), self._tanya("Nama"), self._tanya("No HP"))
            print("Ditambahkan:", m)
        elif p == "2":
            nim = self._tanya("NIM yang diedit")
            print("(kosongkan bila tidak diubah)")
            print("Diubah:", self.mhs.edit(nim, self._tanya("Nama baru"), self._tanya("No HP baru")))
        elif p == "3":
            self.mhs.hapus(self._tanya("NIM yang dihapus"))
            print("Mahasiswa dihapus.")
        elif p == "4":
            self._cetak(self.mhs.cari(self._tanya("NIM / nama")), "Hasil pencarian")
        elif p == "5":
            self._cetak(self.mhs.semua(), "Semua mahasiswa")

    def kelola_alat(self):
        print("\n1.Tambah 2.Edit 3.Hapus 4.Cari 5.Lihat semua")
        p = self._tanya("Pilih")
        if p == "1":
            print("Kategori tersedia:", ", ".join(self.alat.daftar_kategori()), "(boleh ketik kategori baru)")
            kode, nama, kat = self._tanya("Kode alat"), self._tanya("Nama alat"), self._tanya("Kategori")
            print("Kondisi awal:")
            a = self.alat.tambah(kode, nama, kat, self._pilih_kondisi())
            print("Ditambahkan:", a)
        elif p == "2":
            kode = self._tanya("Kode alat yang diedit")
            print("(kosongkan bila tidak diubah)")
            print("Diubah:", self.alat.edit(kode, self._tanya("Nama baru"), self._tanya("Kategori baru")))
        elif p == "3":
            self.alat.hapus(self._tanya("Kode alat yang dihapus"))
            print("Alat dihapus.")
        elif p == "4":
            self.cari_alat()
        elif p == "5":
            self._cetak(self.alat.semua(), "Semua alat")

    def cari_alat(self):
        print("Cari berdasarkan: 1.Kode 2.Nama 3.Kategori 4.Semua")
        mode = {"1": "kode", "2": "nama", "3": "kategori", "4": "semua"}.get(self._tanya("Pilih"))
        if mode is None:
            raise ValidasiError("Pilihan tidak valid.")
        self._cetak(self.alat.cari(self._tanya("Kata kunci"), mode), "Hasil pencarian alat")

    def kelola_kategori(self):
        print("Kategori saat ini:", ", ".join(self.alat.daftar_kategori()))
        baru = self._tanya("Kategori baru (kosong = batal)")
        if baru:
            print("Kategori ditambahkan:", self.alat.tambah_kategori(baru))

    def pemeliharaan(self):
        self._cetak(self.alat.daftar_rusak(), "Alat rusak (belum dipelihara)")
        self._cetak(self.alat.daftar_pemeliharaan(), "Alat dalam pemeliharaan")
        print("\n1.Kirim ke pemeliharaan 2.Selesai diperbaiki")
        p = self._tanya("Pilih")
        if p == "1":
            print("Dimasukkan:", self.alat.kirim_ke_pemeliharaan(self._tanya("Kode alat")))
        elif p == "2":
            print("Kembali tersedia:", self.alat.selesai_pemeliharaan(self._tanya("Kode alat")))

    def buat_transaksi(self):
        self._cetak(self.alat.daftar_tersedia(), "Alat tersedia")
        nim = self._tanya("NIM peminjam")
        kode = self._tanya("Kode alat (pisahkan dengan koma)").split(",")
        lama = self._tanya(f"Lama pinjam hari (1-{max_hari}, kosong = {max_hari})")
        if lama and not lama.isdecimal():
            raise ValidasiError("Lama pinjam harus berupa angka.")
        trx = self.trx.buat(nim, kode, int(lama) if lama else max_hari)
        print(f"Transaksi {trx.id} berhasil dibuat. Batas kembali: {trx.batas_kembali}")

    def tampil_transaksi(self):
        self._cetak_transaksi(self.trx.semua(), "Semua transaksi")

    def proses_pengembalian(self):
        id_trx = self._tanya("ID transaksi")
        trx = self.trx.ambil(id_trx)
        print("Alat yang belum kembali:", ", ".join(trx.belum_kembali()) or "-")
        pengembalian = {}
        while True:
            kode = self._tanya("Kode alat yang dikembalikan (kosong = selesai input)")
            if not kode:
                break
            pengembalian[kode] = self._pilih_kondisi()
        tanggal = self._tanya_tanggal()
        self.trx.kembalikan(id_trx, pengembalian, tanggal)
        print(f"Pengembalian dicatat. Status transaksi: {trx.status}")

    def cari_transaksi(self):
        self._cetak_transaksi(self.trx.cari_by_mahasiswa(self._tanya("NIM / nama mahasiswa")), "Transaksi mahasiswa")

    def riwayat_mahasiswa(self):
        self._cetak_transaksi(self.trx.riwayat(self._tanya("NIM")), "Riwayat peminjaman")

    def statistik(self):
        print("\n== Statistik Peminjaman ==")
        print("Alat paling sering dipinjam:")
        for kode, n in self.stat.alat_terbanyak():
            print(f"  - {kode} {self._nama_alat(kode)}: {n}x")
        print("Mahasiswa paling sering meminjam:")
        for nim, n in self.stat.mahasiswa_terbanyak():
            print(f"  - {nim} {self._nama_mhs(nim)}: {n} transaksi")
        print(f"Transaksi selesai: {self.stat.jumlah_selesai()} | aktif: {self.stat.jumlah_aktif()}")

    def tampil_log(self):
        baris = self.log.format_baris()
        print(f"\n== Log Aktivitas ({len(baris)}) ==")
        for b in baris:
            print(b)

    def data_contoh(self):
        muat_data_contoh(self.mhs, self.alat)
        print("Data contoh dimuat (4 mahasiswa, 8 alat).")
