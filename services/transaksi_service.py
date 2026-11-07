from datetime import date

from models.exceptions import (AturanBisnisError, DataTidakDitemukanError, ValidasiError)
from models.transaksi import max_hari, Transaksi


class TransaksiService:
    """Mengelola peminjaman & pengembalian. Data: dict {id: Transaksi}.

    `_per_mahasiswa` adalah indeks {nim: [id, ...]} agar riwayat mahasiswa
    tidak perlu memindai seluruh transaksi.
    """

    MAKS_TRANSAKSI_AKTIF = 2

    def __init__(self, mahasiswa_service, alat_service, log):
        self._mhs = mahasiswa_service
        self._alat = alat_service
        self._log = log
        self._data = {}
        self._per_mahasiswa = {}
        self._urut = 0

    def buat(self, nim, daftar_kode, lama_hari=max_hari, tanggal=None):
        tanggal = tanggal or date.today()
        mhs = self._mhs.ambil(nim)
        if not 1 <= lama_hari <= max_hari:
            raise ValidasiError(f"Lama peminjaman harus 1-{max_hari} hari.")
        kode_list = list(dict.fromkeys(k.strip().upper() for k in daftar_kode if k.strip()))
        if not kode_list:
            raise ValidasiError("Minimal satu alat harus dipilih.")
        # Aturan 2
        if len(mhs.transaksi_aktif) >= self.MAKS_TRANSAKSI_AKTIF:
            raise AturanBisnisError(
                f"Mahasiswa {nim} sudah memiliki {self.MAKS_TRANSAKSI_AKTIF} transaksi aktif."
            )
        # Aturan 1 - validasi SEMUA alat dulu sebelum ada perubahan data (atomic)
        alat_list = [self._alat.ambil(k) for k in kode_list]
        tidak_tersedia = [f"{a.kode} ({a.nama}, {a.status})" for a in alat_list if not a.tersedia]
        if tidak_tersedia:
            raise AturanBisnisError("Transaksi ditolak, alat tidak tersedia: " + ", ".join(tidak_tersedia))

        self._urut += 1
        id_trx = f"T{self._urut:03d}"
        trx = Transaksi(id_trx, nim, kode_list, tanggal, lama_hari)
        for a in alat_list:
            a.pinjam(id_trx)
        mhs.transaksi_aktif.append(id_trx)
        self._data[id_trx] = trx
        self._per_mahasiswa.setdefault(nim, []).append(id_trx)

        self._log.catat(f"Transaksi {id_trx} dibuat oleh mahasiswa {nim}")
        for a in alat_list:
            self._log.catat(f"Alat {a.kode} ({a.nama}) dipinjam pada transaksi {id_trx}")
        return trx

    def kembalikan(self, id_trx, pengembalian, tanggal=None):
        """pengembalian: dict {kode_alat: kondisi}. Boleh sebagian (Aturan 4)."""
        tanggal = tanggal or date.today()
        trx = self.ambil(id_trx)
        if not trx.aktif:
            raise AturanBisnisError(f"Transaksi {id_trx} sudah selesai.")
        if not pengembalian:
            raise ValidasiError("Pilih minimal satu alat yang dikembalikan.")
        pengembalian = {k.strip().upper(): v for k, v in pengembalian.items()}
        for kode, kondisi in pengembalian.items():  # validasi semua dulu
            trx.validasi_pengembalian(kode, kondisi, tanggal)

        hasil = []
        for kode, kondisi in pengembalian.items():
            detail = trx.catat_pengembalian(kode, kondisi, tanggal)
            alat = self._alat.ambil(kode)
            alat.kembalikan(kondisi)  # Aturan 5
            self._log.catat(
                f"Alat {kode} ({alat.nama}) dikembalikan pada {id_trx} dalam kondisi {kondisi}"
                + (" (TERLAMBAT)" if detail.terlambat else "")
            )
            hasil.append(detail)

        if not trx.aktif:
            self._mhs.ambil(trx.nim).transaksi_aktif.remove(trx.id)
            for k in trx.items:
                self._alat.ambil(k).transaksi_aktif.remove(trx.id)  # alat tidak lagi tercatat di transaksi aktif
            self._log.catat(f"Transaksi {trx.id} selesai")
        return hasil

    def muat(self, daftar):
        """Ganti seluruh transaksi dengan data dari file, lalu sambungkan ulang status aktifnya.

        Mahasiswa dan alat harus sudah dimuat lebih dulu. Bila data tidak konsisten,
        DataTidakDitemukanError dilempar (dibungkus menjadi PenyimpananError oleh pemanggil).
        """
        self._data = {t.id: t for t in daftar}
        self._per_mahasiswa = {}
        for t in daftar:
            self._per_mahasiswa.setdefault(t.nim, []).append(t.id)
        self._urut = max((int(t.id[1:]) for t in daftar if t.id[1:].isdigit()), default=0)
        for t in daftar:
            if t.aktif:
                self._mhs.ambil(t.nim).transaksi_aktif.append(t.id)
                for kode in t.items:
                    self._alat.ambil(kode).transaksi_aktif.append(t.id)

    def ambil(self, id_trx):
        trx = self._data.get(id_trx.strip().upper())
        if trx is None:
            raise DataTidakDitemukanError(f"Transaksi {id_trx} tidak ditemukan.")
        return trx

    def semua(self):
        return list(self._data.values())

    def aktif(self):
        return [t for t in self._data.values() if t.aktif]

    def selesai(self):
        return [t for t in self._data.values() if not t.aktif]

    def cari_by_mahasiswa(self, keyword):
        """Cari transaksi berdasarkan NIM atau (sebagian) nama mahasiswa."""
        hasil = []
        for mhs in self._mhs.cari(keyword):
            hasil.extend(self._data[i] for i in self._per_mahasiswa.get(mhs.nim, []))
        return hasil

    def riwayat(self, nim):
        self._mhs.ambil(nim)  # pastikan mahasiswa ada
        return [self._data[i] for i in self._per_mahasiswa.get(nim, [])]
