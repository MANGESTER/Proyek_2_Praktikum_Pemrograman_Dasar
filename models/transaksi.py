from datetime import timedelta
from models.alat import cek_kondisi
from models.exceptions import AturanBisnisError, DataTidakDitemukanError

status_dipinjam = 'Dipinjam'
status_sebagian = 'Hanya Sebagian yang Dikembalikan'
status_selesai = 'selesai'
max_hari = 7
status_valid = (status_dipinjam, status_sebagian, status_selesai)

class DetailPinjam:
    def __init__(self, kode_alat):
        self.kode_alat = kode_alat
        self.tanggal_kembali = None
        self.kondisi_kembali = None
        self.terlambat = False

    @property
    def sudah_kembali(self):
        return self.tanggal_kembali is not None

class Transaksi:
    def __init__(self, id_transaksi, nim, daftar_kode, tanggal_pinjam, lama_hari=max_hari):
        self.id = id_transaksi
        self.nim = nim 
        self.items = {kode: DetailPinjam(kode) for kode in daftar_kode}
        self.tanggal_pinjam = tanggal_pinjam
        self.batas_kembali = tanggal_pinjam + timedelta(days=lama_hari)
        self.status = status_dipinjam

    @property
    def aktif(self):
        return self.status != status_selesai

    def belum_kembali(self):
        return [k for k, d in self.items.items() if not d.sudah_kembali]

    def validasi_pengembalian(self, kode, kondisi, tanggal):
        detail = self.items.get(kode)

        if detail is None:
            raise DataTidakDitemukanError(f'Alat {kode} tidak ada diriwayat transaksi {self.id}.')
        if detail.sudah_kembali:
            raise AturanBisnisError(f'Alat {kode} sudah dikembalikan sebelumnya.')

        cek_kondisi(kondisi)
        if tanggal < self.tanggal_pinjam:
            raise AturanBisnisError('Tanggal pengembalian tidak boleh sebelum tanggal peminjaman.')

    def catat_pengembalian(self, kode, kondisi, tanggal):
        self.validasi_pengembalian(kode, kondisi, tanggal)
        detail = self.items[kode]
        detail.tanggal_kembali = tanggal
        detail.kondisi_kembali = kondisi 
        detail.terlambat = tanggal > self.batas_kembali

        self.status = status_selesai if not self.belum_kembali() else status_sebagian
        return detail