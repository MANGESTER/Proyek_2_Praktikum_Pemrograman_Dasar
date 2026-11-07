from models.exceptions import AturanBisnisError, ValidasiError

Kondisi_Baik = 'Baik'
Kondisi_Rusak_Ringan = 'Rusak Ringan'
Kondisi_Rusak_Berat = 'Rusak Berat'
Kondisi_Valid = (Kondisi_Baik, Kondisi_Rusak_Ringan, Kondisi_Rusak_Berat)

Status_Tersedia = 'Tersedia'
Status_Dipinjam = 'Dipinjam'
Status_Rusak = 'Rusak'
Status_Pemeliharaan = 'Pemeliharaan'
Status_Valid = (Status_Tersedia, Status_Dipinjam, Status_Rusak, Status_Pemeliharaan)

def cek_kondisi(kondisi):
    if kondisi not in Kondisi_Valid:
        raise ValidasiError(f"Kondisi harus salah satu dari: {', '.join(Kondisi_Valid)}")
    return kondisi

class Alat:
    def __init__(self, kode, nama, kategori, kondisi=Kondisi_Baik):
        self.kode = kode
        self.nama = nama
        self.kategori = kategori
        self.kondisi = cek_kondisi(kondisi)
        self.status = Status_Tersedia if kondisi == Kondisi_Baik else Status_Rusak
        # ID transaksi AKTIF yang masih mencatat alat ini (dipakai Aturan 6)
        self.transaksi_aktif = []

    @property
    def tersedia(self):
        return self.status == Status_Tersedia

    def pinjam(self, id_transaksi):
        if not self.tersedia:
            raise AturanBisnisError(f'Alat {self.kode} ({self.nama}) tidak tersedia (status: {self.status})')
        self.status = Status_Dipinjam
        self.transaksi_aktif.append(id_transaksi)

    def kembalikan(self, kondisi):
        self.kondisi = cek_kondisi(kondisi)
        # transaksi_aktif sengaja tidak dihapus di sini: dilepas TransaksiService saat transaksi selesai
        self.status = Status_Tersedia if kondisi == Kondisi_Baik else Status_Rusak

    def kirim_ke_pemeliharaan(self):
        if self.status != Status_Rusak:
            raise AturanBisnisError(f"Hanya alat berstatus 'Rusak' yang dapat dipelihara (status {self.kode}: {self.status})")
        self.status = Status_Pemeliharaan

    def selesai_pemeliharaan(self):
        if self.status != Status_Pemeliharaan:
            raise AturanBisnisError(f'Alat {self.kode} tidak sedang dalam pemeliharaan')
        self.kondisi = Kondisi_Baik
        self.status = Status_Tersedia

    def __str__(self):
        return f'{self.kode} | {self.nama} | {self.kategori} | Kondisi: {self.kondisi} | Status: {self.status}'
