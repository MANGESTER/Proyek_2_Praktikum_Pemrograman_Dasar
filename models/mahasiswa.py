class Mahasiswa:
    def __init__(self, nim, nama, no_hp):
        self.nim = nim
        self.nama = nama 
        self.no_hp = no_hp
        self.transaksi_aktif = []

    @property
    def status_aktif(self):
        return len(self.transaksi_aktif) > 0

    def __str__(self):
        status = 'aktif meminjam' if self.status_aktif else 'tidak meminjam'
        return f'{self.nim} | {self.nama} | {self.no_hp} | {status}' 