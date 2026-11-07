from models.exceptions import AturanBisnisError, DataSudahAdaError, DataTidakDitemukanError, ValidasiError
from models.mahasiswa import Mahasiswa
from utils.validasi import wajib


class MahasiswaService:
    """CRUD mahasiswa. Data disimpan di dict {nim: Mahasiswa} (akses O(1))."""

    def __init__(self, log):
        self._data = {}
        self._log = log

    @staticmethod
    def _cek_hp(no_hp):
        no_hp = wajib(no_hp, "Nomor HP")
        if not no_hp.isdigit() or not 8 <= len(no_hp) <= 15:
            raise ValidasiError("Nomor HP harus berupa angka 8-15 digit.")
        return no_hp

    def tambah(self, nim, nama, no_hp):
        nim = wajib(nim, "NIM")
        nama = wajib(nama, "Nama")
        no_hp = self._cek_hp(no_hp)
        if nim in self._data:
            raise DataSudahAdaError(f"NIM {nim} sudah terdaftar.")
        self._data[nim] = Mahasiswa(nim, nama, no_hp)
        self._log.catat(f"Mahasiswa {nim} ditambahkan")
        return self._data[nim]

    def ambil(self, nim):
        mhs = self._data.get(nim)
        if mhs is None:
            raise DataTidakDitemukanError(f"Mahasiswa dengan NIM {nim} tidak ditemukan.")
        return mhs

    def edit(self, nim, nama=None, no_hp=None):
        mhs = self.ambil(nim)
        # validasi semua input dulu, baru ubah data: edit yang gagal tidak boleh mengubah apa pun
        nama_baru = wajib(nama, "Nama") if nama else None
        hp_baru = self._cek_hp(no_hp) if no_hp else None
        if nama_baru:
            mhs.nama = nama_baru
        if hp_baru:
            mhs.no_hp = hp_baru
        self._log.catat(f"Mahasiswa {nim} diubah")
        return mhs

    def hapus(self, nim):
        """Aturan 6: tidak boleh dihapus bila masih punya transaksi aktif."""
        mhs = self.ambil(nim)
        if mhs.status_aktif:
            raise AturanBisnisError(
                f"Mahasiswa {nim} masih memiliki transaksi aktif ({', '.join(mhs.transaksi_aktif)}); tidak dapat dihapus."
            )
        del self._data[nim]
        self._log.catat(f"Mahasiswa {nim} dihapus")

    def cari(self, keyword):
        k = keyword.strip().lower()
        return [m for m in self._data.values() if k in m.nim.lower() or k in m.nama.lower()]

    def muat(self, daftar):
        """Ganti seluruh data dengan daftar Mahasiswa dari file."""
        self._data = {m.nim: m for m in daftar}

    def semua(self):
        return list(self._data.values())
