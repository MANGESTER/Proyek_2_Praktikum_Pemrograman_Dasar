from collections import Counter


class StatistikService:
    """Tantangan B: statistik peminjaman (dihitung dari data transaksi)."""

    def __init__(self, transaksi_service):
        self._trx = transaksi_service

    @staticmethod
    def _teratas(counter, n):
        return counter.most_common(n)

    def alat_terbanyak(self, n=3):
        c = Counter(kode for t in self._trx.semua() for kode in t.items)
        return self._teratas(c, n)

    def mahasiswa_terbanyak(self, n=3):
        c = Counter(t.nim for t in self._trx.semua())
        return self._teratas(c, n)

    def jumlah_selesai(self):
        return len(self._trx.selesai())

    def jumlah_aktif(self):
        return len(self._trx.aktif())
