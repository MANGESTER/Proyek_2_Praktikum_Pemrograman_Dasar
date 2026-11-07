import os
import tempfile
import unittest
from datetime import date, timedelta

from models.alat import Kondisi_Baik, Kondisi_Rusak_Berat, Status_Dipinjam, Status_Rusak
from models.exceptions import AturanBisnisError, PenyimpananError
from models.transaksi import status_sebagian
from services.alat_service import AlatService
from services.log_service import LogService
from services.mahasiswa_service import MahasiswaService
from services.penyimpanan_csv_service import NAMA_FILE, PenyimpananCsv
from services.transaksi_service import TransaksiService

HARI_INI = date(2026, 8, 10)

def buat_aplikasi(folder):
    """Rangkai satu set service baru yang terhubung ke folder data tertentu."""
    log = LogService()
    mhs = MahasiswaService(log)
    alat = AlatService(log)
    trx = TransaksiService(mhs, alat, log)
    simpanan = PenyimpananCsv(folder, log, mhs, alat, trx)
    return log, mhs, alat, trx, simpanan


class DasarPenyimpanan(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = os.path.join(self._tmp.name, "data")  # sengaja belum ada: harus dibuat otomatis
        self.log, self.mhs, self.alat, self.trx, self.simpanan = buat_aplikasi(self.folder)
        self.mhs.tambah("M001", "Dika", "081234567890")
        self.mhs.tambah("M002", "Abyan", "081234567891")
        for kode, nama, kat in [("A001", "Kamera", "perangkat multimedia"), ("A002", "Tripod", "perangkat multimedia"),
                                ("A003", "Kabel LAN", "perangkat jaringan"), ("A004", "Multimeter", "perangkat elektronik")]:
            self.alat.tambah(kode, nama, kat)

    def tearDown(self):
        self._tmp.cleanup()

    def muat_ulang(self):
        """Simulasi program ditutup lalu dibuka lagi: semua objek baru, hanya file yang sama."""
        log, mhs, alat, trx, simpanan = buat_aplikasi(self.folder)
        simpanan.muat()
        return log, mhs, alat, trx

    def tulis(self, kunci, isi):
        os.makedirs(self.folder, exist_ok=True)
        with open(os.path.join(self.folder, NAMA_FILE[kunci]), "w", encoding="utf-8") as f:
            f.write(isi)

class TestSimpanDanMuat(DasarPenyimpanan):
    def test_simpan_membuat_folder_dan_semua_file_txt(self):
        self.simpanan.simpan()
        for nama in NAMA_FILE.values():
            self.assertTrue(os.path.isfile(os.path.join(self.folder, nama)), nama)
        with open(os.path.join(self.folder, "mahasiswa.csv"), encoding="utf-8") as f:
            isi = f.read()
        self.assertIn("M001;Dika;081234567890", isi)

    def test_tidak_ada_file_sementara_tersisa(self):
        self.simpanan.simpan()
        self.assertEqual([n for n in os.listdir(self.folder) if n.endswith(".tmp")], [])

    def test_folder_kosong_aman_dimuat(self):
        _, mhs, alat, trx, simpanan = buat_aplikasi(os.path.join(self._tmp.name, "belum_ada"))
        simpanan.muat()  # tidak boleh error
        self.assertEqual((mhs.semua(), alat.semua(), trx.semua()), ([], [], []))

    def test_data_master_kembali_utuh(self):
        self.alat.tambah_kategori("perangkat audio")
        self.simpanan.simpan()
        _, mhs, alat, _ = self.muat_ulang()
        self.assertEqual([str(m) for m in mhs.semua()], [str(m) for m in self.mhs.semua()])
        self.assertEqual([str(a) for a in alat.semua()], [str(a) for a in self.alat.semua()])
        self.assertIn("perangkat audio", alat.daftar_kategori())

    def test_transaksi_sebagian_kembali_utuh_setelah_muat(self):
        t = self.trx.buat("M001", ["A001", "A002", "A003"], lama_hari=5, tanggal=HARI_INI)
        self.trx.kembalikan(t.id, {"A001": Kondisi_Baik, "A002": Kondisi_Rusak_Berat}, HARI_INI + timedelta(days=7))
        self.simpanan.simpan()

        _, mhs, alat, trx = self.muat_ulang()
        t2 = trx.ambil(t.id)
        self.assertEqual(t2.status, status_sebagian)
        self.assertEqual(t2.tanggal_pinjam, HARI_INI)
        self.assertEqual(t2.batas_kembali, HARI_INI + timedelta(days=5))
        self.assertEqual(t2.belum_kembali(), ["A003"])
        self.assertEqual(t2.items["A001"].tanggal_kembali, HARI_INI + timedelta(days=7))
        self.assertTrue(t2.items["A001"].terlambat)
        self.assertEqual(t2.items["A002"].kondisi_kembali, Kondisi_Rusak_Berat)
        self.assertIsNone(t2.items["A003"].tanggal_kembali)
        self.assertEqual(alat.ambil("A002").status, Status_Rusak)
        self.assertEqual(alat.ambil("A003").status, Status_Dipinjam)
        self.assertTrue(mhs.ambil("M001").status_aktif)

    def test_id_transaksi_dilanjutkan_setelah_muat(self):
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        self.trx.buat("M002", ["A002"], tanggal=HARI_INI)
        self.simpanan.simpan()
        _, _, _, trx = self.muat_ulang()
        baru = trx.buat("M001", ["A003"], tanggal=HARI_INI)
        self.assertEqual(baru.id, "T003")  # bukan T001 lagi

    def test_aturan_bisnis_tetap_berlaku_setelah_muat(self):
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        self.trx.buat("M001", ["A002"], tanggal=HARI_INI)
        self.simpanan.simpan()
        _, mhs, alat, trx = self.muat_ulang()
        with self.assertRaises(AturanBisnisError):  # Aturan 2
            trx.buat("M001", ["A003"], tanggal=HARI_INI)
        with self.assertRaises(AturanBisnisError):  # Aturan 1
            trx.buat("M002", ["A001"], tanggal=HARI_INI)
        with self.assertRaises(AturanBisnisError):  # Aturan 6 (mahasiswa)
            mhs.hapus("M001")
        with self.assertRaises(AturanBisnisError):  # Aturan 6 (alat)
            alat.hapus("A001")

    def test_pengembalian_setelah_muat_menyelesaikan_transaksi(self):
        t = self.trx.buat("M001", ["A001", "A002"], tanggal=HARI_INI)
        self.trx.kembalikan(t.id, {"A001": Kondisi_Baik}, HARI_INI)
        self.simpanan.simpan()
        _, mhs, alat, trx = self.muat_ulang()
        trx.kembalikan(t.id, {"A002": Kondisi_Baik}, HARI_INI)
        self.assertFalse(trx.ambil(t.id).aktif)
        self.assertFalse(mhs.ambil("M001").status_aktif)
        alat.hapus("A001")  # transaksi selesai -> alat boleh dihapus

    def test_log_tersimpan_dan_dimuat(self):
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        self.simpanan.simpan()
        log, _, _, _ = self.muat_ulang()
        pesan = [e["pesan"] for e in log.semua()]
        self.assertEqual(pesan, [e["pesan"] for e in self.log.semua()])
        self.assertIn("Transaksi T001 dibuat oleh mahasiswa M001", pesan)

    def test_karakter_khusus_dan_unicode_aman(self):
        self.mhs.tambah("M009", 'Budi ; "Santoso", \\ #1\nbaris dua', "081234567899")
        self.alat.tambah("A009", "Café #2 | éè", "kategori | aneh")
        self.simpanan.simpan()
        _, mhs, alat, _ = self.muat_ulang()
        self.assertEqual(mhs.ambil("M009").nama, 'Budi ; "Santoso", \\ #1\nbaris dua')
        self.assertEqual(alat.ambil("A009").nama, "Café #2 | éè")
        self.assertIn("kategori | aneh", alat.daftar_kategori())

    def test_file_bisa_diedit_manual_dengan_baris_kosong(self):
        self.simpanan.simpan()
        path = os.path.join(self.folder, "mahasiswa.csv")
        with open(path, encoding="utf-8") as f:
            isi = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(isi + "\nM003;Ayun;081234567892\n\n")
        _, mhs, _, _ = self.muat_ulang()
        self.assertEqual(mhs.ambil("M003").nama, "Ayun")

    def test_penggantian_file_gagal_di_tengah_dibatalkan_dan_disk_tetap_sinkron(self):
        """Simulasi file dikunci (mis. OneDrive) saat penggantian: file yang sudah terlanjur diganti dikembalikan."""
        from unittest import mock
        self.simpanan.simpan()
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        asli = os.replace

        def ganti_gagal(src, dst):
            if os.path.basename(dst) == "detail_transaksi.csv":
                raise PermissionError(13, "file terkunci")
            return asli(src, dst)
        with mock.patch("services.penyimpanan_csv_service.os.replace", ganti_gagal):
            with self.assertRaises(PenyimpananError):
                self.simpanan.simpan()
        sisa = [n for n in os.listdir(self.folder) if n.endswith((".tmp", ".bak"))]
        self.assertEqual(sisa, [])  # tidak ada file sementara/cadangan tertinggal
        _, mhs, alat, trx = self.muat_ulang()  # disk masih sinkron (keadaan SEBELUM transaksi)
        self.assertEqual(trx.semua(), [])
        self.assertTrue(alat.ambil("A001").tersedia)
        self.simpanan.simpan()  # kunci lepas: simpan berikutnya berhasil
        _, _, alat2, trx2 = self.muat_ulang()
        self.assertEqual([x.id for x in trx2.semua()], ["T001"])
        self.assertEqual(alat2.ambil("A001").status, "Dipinjam")


class TestFileRusak(DasarPenyimpanan):
    def test_jumlah_kolom_salah_menyebut_nama_file_dan_baris(self):
        self.tulis("mahasiswa", "nim;nama;no_hp\nM001;Dika\n")
        with self.assertRaises(PenyimpananError) as ctx:
            self.muat_ulang()
        self.assertIn("mahasiswa.csv baris 2", str(ctx.exception))

    def test_nim_ganda_ditolak(self):
        self.tulis("mahasiswa", "M001;A;081234567890\nM001;B;081234567891\n")
        with self.assertRaises(PenyimpananError):
            self.muat_ulang()

    def test_status_alat_tidak_dikenal(self):
        self.tulis("alat", "A001;Laptop;komputasi;Baik;Hilang\n")
        with self.assertRaises(PenyimpananError):
            self.muat_ulang()

    def test_kondisi_alat_tidak_sah(self):
        self.tulis("alat", "A001;Laptop;komputasi;Hancur;Tersedia\n")
        with self.assertRaises(PenyimpananError):
            self.muat_ulang()

    def test_tanggal_salah_format(self):
        self.tulis("mahasiswa", "M001;Dika;081234567890\n")
        self.tulis("alat", "A001;Laptop;komputasi;Baik;Dipinjam\n")
        self.tulis("transaksi", "T001;M001;10-08-2026;2026-08-17;Dipinjam\n")
        self.tulis("detail", "T001;A001;-;-;0\n")
        with self.assertRaises(PenyimpananError) as ctx:
            self.muat_ulang()
        self.assertIn("YYYY-MM-DD", str(ctx.exception))

    def test_transaksi_aktif_dengan_mahasiswa_tidak_ada(self):
        self.tulis("alat", "A001;Laptop;komputasi;Baik;Dipinjam\n")
        self.tulis("transaksi", "T001;M404;2026-08-10;2026-08-17;Dipinjam\n")
        self.tulis("detail", "T001;A001;-;-;0\n")
        with self.assertRaises(PenyimpananError):
            self.muat_ulang()

    def test_alat_dipinjam_tanpa_transaksi_aktif(self):
        self.tulis("alat", "A001;Laptop;komputasi;Baik;Dipinjam\n")
        with self.assertRaises(PenyimpananError):
            self.muat_ulang()

    def test_detail_untuk_transaksi_yang_tidak_ada(self):
        self.tulis("detail", "T777;A001;-;-;0\n")
        with self.assertRaises(PenyimpananError):
            self.muat_ulang()

    def test_transaksi_tanpa_detail(self):
        self.tulis("mahasiswa", "M001;Dika;081234567890\n")
        self.tulis("transaksi", "T001;M001;2026-08-10;2026-08-17;selesai\n")
        with self.assertRaises(PenyimpananError):
            self.muat_ulang()


class TestPerbaikanTahap2(DasarPenyimpanan):
    def test_file_berbom_tidak_menghasilkan_data_palsu(self):
        self.simpan_lalu_tambah_bom("mahasiswa.csv")
        _, mhs, _, _ = self.muat_ulang()
        self.assertEqual(sorted(m.nim for m in mhs.semua()), ["M001", "M002"])

    def simpan_lalu_tambah_bom(self, nama):
        self.simpanan.simpan()
        path = os.path.join(self.folder, nama)
        with open(path, "rb") as f:
            isi = f.read().lstrip(b"\xef\xbb\xbf")
        with open(path, "wb") as f:
            f.write(b"\xef\xbb\xbf" + isi)

    def test_kondisi_dan_status_alat_harus_cocok(self):
        self.tulis("alat", "A001;Laptop;komputasi;Rusak Berat;Tersedia\n")
        with self.assertRaises(PenyimpananError) as ctx:
            self.muat_ulang()
        self.assertIn("alat.csv baris 1", str(ctx.exception))
        self.tulis("alat", "A001;Laptop;komputasi;Baik;Rusak\n")
        with self.assertRaises(PenyimpananError):
            self.muat_ulang()

    def test_status_transaksi_harus_sesuai_detail(self):
        self.tulis("mahasiswa", "M001;Dika;081234567890\n")
        self.tulis("alat", "A001;Laptop;komputasi;Baik;Dipinjam\n")
        self.tulis("transaksi", "T001;M001;2026-08-10;2026-08-17;selesai\n")  # padahal alat belum kembali
        self.tulis("detail", "T001;A001;-;-;0\n")
        with self.assertRaises(PenyimpananError) as ctx:
            self.muat_ulang()
        self.assertIn("tidak sesuai dengan detail", str(ctx.exception))

    def test_tanggal_dan_kondisi_kembali_harus_berpasangan(self):
        self.tulis("mahasiswa", "M001;Dika;081234567890\n")
        self.tulis("alat", "A001;Laptop;komputasi;Baik;Dipinjam\n")
        self.tulis("transaksi", "T001;M001;2026-08-10;2026-08-17;Dipinjam\n")
        self.tulis("detail", "T001;A001;2026-08-11;-;0\n")
        with self.assertRaises(PenyimpananError):
            self.muat_ulang()

    def test_alat_belum_kembali_di_dua_transaksi_aktif_ditolak(self):
        self.trx.buat("M001", ["A001"], tanggal=HARI_INI)
        self.trx.buat("M002", ["A002"], tanggal=HARI_INI)
        self.simpanan.simpan()
        path = os.path.join(self.folder, "detail_transaksi.csv")
        with open(path, encoding="utf-8") as f:
            isi = f.read().replace("T002;A002", "T002;A001")
        with open(path, "w", encoding="utf-8") as f:
            f.write(isi)
        with self.assertRaises(PenyimpananError) as ctx:
            self.muat_ulang()
        self.assertIn("lebih dari satu transaksi aktif", str(ctx.exception))

    def test_kategori_milik_alat_terdaftar_walau_kategori_txt_hilang(self):
        self.simpanan.simpan()
        os.remove(os.path.join(self.folder, "kategori.csv"))
        _, _, alat, _ = self.muat_ulang()
        self.assertIn("perangkat elektronik", alat.daftar_kategori())

    def test_simpan_tidak_menulis_ulang_bila_tidak_ada_perubahan(self):
        from unittest import mock
        self.simpanan.simpan()
        with mock.patch("services.penyimpanan_csv_service.os.replace") as ganti:
            self.simpanan.simpan()
            self.assertEqual(ganti.call_count, 0)
        self.mhs.edit("M001", "Dika Baru")
        with mock.patch("services.penyimpanan_csv_service.os.replace", wraps=os.replace) as ganti:
            self.simpanan.simpan()
            nama_ditulis = {os.path.basename(c.args[1]) for c in ganti.call_args_list}
        self.assertEqual(nama_ditulis, {"mahasiswa.csv", "log.csv"})  # hanya yang berubah

    def test_file_yang_hilang_ditulis_ulang(self):
        self.simpanan.simpan()
        os.remove(os.path.join(self.folder, "alat.csv"))
        self.simpanan.simpan()
        self.assertTrue(os.path.isfile(os.path.join(self.folder, "alat.csv")))

    def test_data_contoh_dimuat_seluruhnya_atau_tidak_sama_sekali(self):
        from data_contoh import muat_data_contoh
        from models.exceptions import DataSudahAdaError
        log, mhs, alat, trx, _ = buat_aplikasi(os.path.join(self._tmp.name, "kosong"))
        mhs.tambah("M003", "Ayun", "081234567892")  # bentrok dengan data contoh
        with self.assertRaises(DataSudahAdaError):
            muat_data_contoh(mhs, alat)
        self.assertEqual([m.nim for m in mhs.semua()], ["M003"])  # tidak ada yang setengah masuk
        self.assertEqual(alat.semua(), [])


class TestFormatCsv(DasarPenyimpanan):
    def test_baris_judul_dan_bom_ditulis_untuk_excel(self):
        self.simpanan.simpan()
        with open(os.path.join(self.folder, "mahasiswa.csv"), "rb") as f:
            mentah = f.read()
        self.assertTrue(mentah.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(mentah.decode("utf-8-sig").startswith("nim;nama;no_hp\r\n"))

    def test_file_tanpa_baris_judul_tetap_terbaca(self):
        self.tulis("mahasiswa", "M001;Dika;081234567890\nM002;Abyan;081234567891\n")
        _, mhs, _, _ = self.muat_ulang()
        self.assertEqual(sorted(m.nim for m in mhs.semua()), ["M001", "M002"])

    def test_pemisah_koma_dikenali_otomatis(self):
        self.tulis("mahasiswa", 'nim,nama,no_hp\nM001,"Dika, S.Kom",081234567890\n')
        _, mhs, _, _ = self.muat_ulang()
        self.assertEqual(mhs.ambil("M001").nama, "Dika, S.Kom")

    def test_hasil_simpan_excel_dengan_kolom_kosong_di_ujung(self):
        self.tulis("mahasiswa", "nim;nama;no_hp;;\r\nM001;Dika;081234567890;;\r\n;;;;\r\n")
        _, mhs, _, _ = self.muat_ulang()
        self.assertEqual([m.nim for m in mhs.semua()], ["M001"])

    def test_file_cp1252_bukan_utf8_tetap_terbaca(self):
        os.makedirs(self.folder, exist_ok=True)
        with open(os.path.join(self.folder, "mahasiswa.csv"), "wb") as f:
            f.write("nim;nama;no_hp\nM001;Caf\u00e9 Dika;081234567890\n".encode("cp1252"))
        _, mhs, _, _ = self.muat_ulang()
        self.assertEqual(mhs.ambil("M001").nama, "Caf\u00e9 Dika")

    def test_tanggal_hasil_format_excel_ditolak_dengan_pesan_jelas(self):
        self.tulis("mahasiswa", "M001;Dika;081234567890\n")
        self.tulis("alat", "A001;Laptop;komputasi;Baik;Dipinjam\n")
        self.tulis("transaksi", "T001;M001;10/08/2026;17/08/2026;Dipinjam\n")
        self.tulis("detail", "T001;A001;-;-;0\n")
        with self.assertRaises(PenyimpananError) as ctx:
            self.muat_ulang()
        self.assertIn("transaksi.csv baris 1", str(ctx.exception))
        self.assertIn("YYYY-MM-DD", str(ctx.exception))

    def test_tanda_kutip_tidak_seimbang_ditolak(self):
        self.tulis("mahasiswa", 'M001;"Dika;081234567890\n')
        with self.assertRaises(PenyimpananError):
            self.muat_ulang()


if __name__ == "__main__":
    unittest.main()
