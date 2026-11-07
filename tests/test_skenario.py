"""Pengujian otomatis: skenario wajib 1-6 + aturan bisnis tambahan + tantangan."""
import unittest
from datetime import date, timedelta

from models.alat import Kondisi_Baik, Kondisi_Rusak_Berat, Kondisi_Rusak_Ringan
from models.transaksi import status_dipinjam, status_sebagian, status_selesai
from models.exceptions import AturanBisnisError, DataSudahAdaError, DataTidakDitemukanError, ValidasiError
from services.alat_service import AlatService
from services.log_service import LogService
from services.mahasiswa_service import MahasiswaService
from services.statistik_service import StatistikService
from services.transaksi_service import TransaksiService

HARI_INI = date(2026, 8, 10)


class DasarTest(unittest.TestCase):
    def setUp(self):
        self.log = LogService()
        self.mhs = MahasiswaService(self.log)
        self.alat = AlatService(self.log)
        self.trx = TransaksiService(self.mhs, self.alat, self.log)
        self.stat = StatistikService(self.trx)
        # Skenario 1: data awal
        self.mhs.tambah("M001", "Dika", "081234567890")
        self.mhs.tambah("M002", "Abyan", "081234567891")
        for kode, nama, kat in [("A001", "Kamera Digital", "perangkat multimedia"),
                                ("A002", "Tripod", "perangkat multimedia"),
                                ("A003", "Kabel LAN", "perangkat jaringan"),
                                ("A004", "Multimeter", "perangkat elektronik")]:
            self.alat.tambah(kode, nama, kat)


class TestSkenarioWajib(DasarTest):
    def test_skenario1_tambah_data_dan_kategori_baru(self):
        self.assertEqual(len(self.mhs.semua()), 2)
        self.assertEqual(len(self.alat.semua()), 4)
        self.assertIn("perangkat elektronik", self.alat.daftar_kategori())  # kategori baru tanpa ubah kode
        with self.assertRaises(DataSudahAdaError):
            self.mhs.tambah("M001", "Duplikat", "081234567890")

    def test_skenario2_pinjam_beberapa_alat_satu_transaksi(self):
        t = self.trx.buat("M001", ["A001", "A002", "A003"], tanggal=HARI_INI)
        self.assertEqual(len(t.items), 3)
        self.assertEqual(t.status, status_dipinjam)
        self.assertEqual(t.batas_kembali, HARI_INI + timedelta(days=7))
        self.assertEqual({a.kode for a in self.alat.daftar_dipinjam()}, {"A001", "A002", "A003"})
        self.assertEqual([a.kode for a in self.alat.daftar_tersedia()], ["A004"])
        self.assertTrue(self.mhs.ambil("M001").status_aktif)

    def test_skenario3_alat_tidak_tersedia_ditolak(self):
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        with self.assertRaises(AturanBisnisError):
            self.trx.buat("M002", ["A004", "A001"], tanggal=HARI_INI)
        # atomic: A004 tidak ikut terpinjam
        self.assertTrue(self.alat.ambil("A004").tersedia)
        self.assertEqual(len(self.trx.semua()), 1)

    def test_skenario4_pengembalian_sebagian(self):
        t = self.trx.buat("M001", ["A001", "A002", "A003"], tanggal=HARI_INI)
        self.trx.kembalikan(t.id, {"A001": Kondisi_Baik}, HARI_INI + timedelta(days=2))
        self.assertEqual(t.status, status_sebagian)
        self.assertTrue(t.aktif)
        self.assertTrue(self.alat.ambil("A001").tersedia)
        self.assertEqual({a.kode for a in self.alat.daftar_dipinjam()}, {"A002", "A003"})
        self.assertEqual(t.belum_kembali(), ["A002", "A003"])
        self.assertTrue(self.mhs.ambil("M001").status_aktif)  # masih aktif
        self.trx.kembalikan(t.id, {"A002": Kondisi_Baik, "A003": Kondisi_Baik}, HARI_INI + timedelta(days=3))
        self.assertEqual(t.status, status_selesai)
        self.assertFalse(self.mhs.ambil("M001").status_aktif)

    def test_skenario5_kondisi_rusak_tidak_tersedia(self):
        t = self.trx.buat("M001", ["A001", "A002", "A003"], tanggal=HARI_INI)
        self.trx.kembalikan(t.id, {"A001": Kondisi_Baik, "A002": Kondisi_Rusak_Ringan, "A003": Kondisi_Rusak_Berat}, HARI_INI)
        self.assertTrue(self.alat.ambil("A001").tersedia)
        self.assertFalse(self.alat.ambil("A002").tersedia)
        self.assertFalse(self.alat.ambil("A003").tersedia)
        self.assertEqual({a.kode for a in self.alat.daftar_rusak()}, {"A002", "A003"})

    def test_skenario6_hapus_mahasiswa_aktif_ditolak(self):
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        with self.assertRaises(AturanBisnisError):
            self.mhs.hapus("M001")
        with self.assertRaises(AturanBisnisError):  # hapus alat yang sedang dipinjam
            self.alat.hapus("A001")
        self.mhs.hapus("M002")  # tidak aktif -> boleh
        self.assertEqual(len(self.mhs.semua()), 1)


class TestAturanTambahan(DasarTest):
    def test_maks_dua_transaksi_aktif(self):
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        self.trx.buat("M001", ["A002"], tanggal=HARI_INI)
        with self.assertRaises(AturanBisnisError):
            self.trx.buat("M001", ["A003"], tanggal=HARI_INI)

    def test_lama_pinjam_maks_7_hari(self):
        with self.assertRaises(ValidasiError):
            self.trx.buat("M001", ["A001"], lama_hari=8, tanggal=HARI_INI)

    def test_alat_tidak_ditemukan_dan_kode_duplikat_di_input(self):
        with self.assertRaises(DataTidakDitemukanError):
            self.trx.buat("M001", ["X999"], tanggal=HARI_INI)
        t = self.trx.buat("M001", ["a001", "A001"], tanggal=HARI_INI)
        self.assertEqual(list(t.items), ["A001"])

    def test_keterlambatan_tercatat(self):
        t = self.trx.buat("M001", ["A001"], lama_hari=3, tanggal=HARI_INI)
        self.trx.kembalikan(t.id, {"A001": Kondisi_Baik}, HARI_INI + timedelta(days=5))
        self.assertTrue(t.items["A001"].terlambat)

    def test_kembalikan_alat_dua_kali_ditolak(self):
        t = self.trx.buat("M001", ["A001", "A002"], tanggal=HARI_INI)
        self.trx.kembalikan(t.id, {"A001": Kondisi_Baik}, HARI_INI)
        with self.assertRaises(AturanBisnisError):
            self.trx.kembalikan(t.id, {"A001": Kondisi_Baik}, HARI_INI)

    def test_riwayat_dan_cari_transaksi_mahasiswa(self):
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        self.assertEqual(len(self.trx.riwayat("M001")), 1)
        self.assertEqual(len(self.trx.cari_by_mahasiswa("dik")), 1)
        self.assertEqual(self.trx.cari_by_mahasiswa("abyan"), [])


class TestTantangan(DasarTest):
    def test_a_pencarian_fleksibel(self):
        self.assertEqual([a.kode for a in self.alat.cari("A003", "kode")], ["A003"])
        self.assertEqual([a.kode for a in self.alat.cari("kamera", "nama")], ["A001"])
        self.assertEqual(len(self.alat.cari("multimedia", "kategori")), 2)

    def test_b_statistik(self):
        t1 = self.trx.buat("M001", ["A001", "A002"], tanggal=HARI_INI)
        self.trx.kembalikan(t1.id, {"A001": Kondisi_Baik, "A002": Kondisi_Baik}, HARI_INI)
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        self.assertEqual(self.stat.alat_terbanyak(1), [("A001", 2)])
        self.assertEqual(self.stat.mahasiswa_terbanyak(1), [("M001", 2)])
        self.assertEqual((self.stat.jumlah_selesai(), self.stat.jumlah_aktif()), (1, 1))

    def test_c_pemeliharaan(self):
        t = self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        self.trx.kembalikan(t.id, {"A001": Kondisi_Rusak_Berat}, HARI_INI)
        self.alat.kirim_ke_pemeliharaan("A001")
        self.assertEqual([a.kode for a in self.alat.daftar_pemeliharaan()], ["A001"])
        self.alat.selesai_pemeliharaan("A001")
        self.assertTrue(self.alat.ambil("A001").tersedia)
        with self.assertRaises(AturanBisnisError):
            self.alat.kirim_ke_pemeliharaan("A004")  # alat baik tidak bisa dipelihara

    def test_d_log_aktivitas(self):
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        pesan = " ".join(e["pesan"] for e in self.log.semua())
        self.assertIn("Mahasiswa M001 ditambahkan", pesan)
        self.assertIn("Transaksi T001 dibuat", pesan)


class TestPerbaikanBug(DasarTest):
    def test_alat_sudah_kembali_tapi_transaksi_aktif_tidak_boleh_dihapus(self):
        t = self.trx.buat("M001", ["A001", "A002"], tanggal=HARI_INI)
        self.trx.kembalikan(t.id, {"A001": Kondisi_Baik}, HARI_INI)
        with self.assertRaises(AturanBisnisError):  # A001 masih tercatat di transaksi aktif
            self.alat.hapus("A001")
        self.trx.kembalikan(t.id, {"A002": Kondisi_Baik}, HARI_INI)
        self.alat.hapus("A001")  # transaksi selesai -> boleh
        self.assertEqual(len(self.alat.semua()), 3)

    def test_kategori_tidak_tersimpan_bila_tambah_alat_gagal(self):
        with self.assertRaises(ValidasiError):
            self.alat.tambah("A009", "X", "kategori baru", "hancur")
        self.assertNotIn("kategori baru", self.alat.daftar_kategori())
        self.assertEqual(len(self.alat.semua()), 4)

    def test_alat_dipinjam_ulang_saat_transaksi_lama_masih_aktif(self):
        t1 = self.trx.buat("M001", ["A001", "A002"], tanggal=HARI_INI)
        self.trx.kembalikan(t1.id, {"A001": Kondisi_Baik}, HARI_INI)
        t2 = self.trx.buat("M002", ["A001"], tanggal=HARI_INI)
        self.trx.kembalikan(t2.id, {"A001": Kondisi_Baik}, HARI_INI)
        with self.assertRaises(AturanBisnisError):  # masih tercatat di t1 (aktif)
            self.alat.hapus("A001")
        self.trx.kembalikan(t1.id, {"A002": Kondisi_Baik}, HARI_INI)
        self.alat.hapus("A001")

    def test_edit_gagal_tidak_mengubah_data(self):
        with self.assertRaises(ValidasiError):  # nama valid, nomor HP salah
            self.mhs.edit("M001", "Nama Baru", "abc")
        self.assertEqual(self.mhs.ambil("M001").nama, "Dika")
        with self.assertRaises(ValidasiError):  # nama valid, kategori hanya spasi
            self.alat.edit("A001", "Nama Alat Baru", "   ")
        self.assertEqual(self.alat.ambil("A001").nama, "Kamera Digital")


if __name__ == "__main__":
    unittest.main()
