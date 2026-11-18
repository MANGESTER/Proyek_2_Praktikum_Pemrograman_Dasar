"""Penyimpanan permanen ke file .csv

Setiap jenis data disimpan di satu file CSV di folder data/.
Baris pertama berisi nama kolom, baris berikutnya berisi data.
Pemisah kolom adalah koma (,). Tanda kutip ditangani otomatis oleh modul csv.

    data/mahasiswa.csv         nim,nama,no_hp
    data/alat.csv              kode,nama,kategori,kondisi,status
    data/kategori.csv          kategori
    data/transaksi.csv         id,nim,tanggal_pinjam,batas_kembali,status
    data/detail_transaksi.csv  id_transaksi,kode_alat,tanggal_kembali,kondisi_kembali,terlambat
    data/log.csv               waktu,pesan

Status "aktif" mahasiswa dan alat TIDAK disimpan; dihitung ulang dari transaksi saat file dimuat,
sehingga tidak mungkin berbeda dengan isi transaksi.

Alur kerja:
    muat()   -> baca semua file CSV, periksa isinya, lalu isi service (dipanggil saat program mulai)
    simpan() -> tulis semua data di memori ke file CSV (dipanggil setelah setiap aksi berhasil)
"""
import csv
import os
from datetime import date

from models.alat import (Alat, Kondisi_Baik, Kondisi_Valid, Status_Dipinjam, Status_Pemeliharaan,
                         Status_Rusak, Status_Tersedia, Status_Valid)
from models.exceptions import LabError, PenyimpananError
from models.mahasiswa import Mahasiswa
from models.transaksi import Transaksi, status_dipinjam, status_sebagian, status_selesai, status_valid

KOSONG = "-"  # penanda nilai kosong (mis. tanggal kembali alat yang belum dikembalikan)
PEMISAH = ","  # pemisah kolom

NAMA_FILE = {
    "mahasiswa": "mahasiswa.csv",
    "alat": "alat.csv",
    "kategori": "kategori.csv",
    "transaksi": "transaksi.csv",
    "detail": "detail_transaksi.csv",
    "log": "log.csv",
}

# nama kolom pertama tiap file; dipakai untuk mengenali (dan melewati) baris judul
KOLOM_PERTAMA = {
    "mahasiswa": "nim",
    "alat": "kode",
    "kategori": "kategori",
    "transaksi": "id",
    "detail": "id_transaksi",
    "log": "waktu",
}


def tanggal_ke_teks(nilai):
    """Ubah tanggal menjadi teks 'YYYY-MM-DD'. Bila kosong (None), hasilnya '-'."""
    if nilai is None:
        return KOSONG
    return nilai.isoformat()


def teks_ke_tanggal(teks):
    """Ubah teks 'YYYY-MM-DD' menjadi tanggal. Teks '-' menjadi None."""
    if teks == KOSONG:
        return None
    return date.fromisoformat(teks)


class PenyimpananCsv:
    """Membaca (muat) dan menulis (simpan) seluruh data aplikasi ke folder berisi file .csv."""

    def __init__(self, folder, log, mahasiswa_service, alat_service, transaksi_service):
        self._folder = folder
        self._log = log
        self._mhs = mahasiswa_service
        self._alat = alat_service
        self._trx = transaksi_service

    @property
    def folder(self):
        return self._folder

    def _path(self, kunci):
        return os.path.join(self._folder, NAMA_FILE[kunci])

    # ------------------------------------------------------------------ MENULIS
    def _tulis_file(self, kunci, judul, daftar_baris):
        """Tulis satu file CSV: baris judul dulu, lalu satu baris untuk setiap data."""
        # utf-8-sig menambah BOM di awal file supaya Excel mengenali huruf berakses
        with open(self._path(kunci), "w", encoding="utf-8-sig", newline="") as f:
            penulis = csv.writer(f, delimiter=PEMISAH)
            penulis.writerow(judul)
            for baris in daftar_baris:
                penulis.writerow(baris)

    def simpan(self):
        """Tulis semua data di memori ke file CSV. Gagal menulis -> PenyimpananError."""
        try:
            os.makedirs(self._folder, exist_ok=True)

            # mahasiswa.csv
            baris = []
            for m in self._mhs.semua():
                baris.append([m.nim, m.nama, m.no_hp])
            self._tulis_file("mahasiswa", ["nim", "nama", "no_hp"], baris)

            # alat.csv
            baris = []
            for a in self._alat.semua():
                baris.append([a.kode, a.nama, a.kategori, a.kondisi, a.status])
            self._tulis_file("alat", ["kode", "nama", "kategori", "kondisi", "status"], baris)

            # kategori.csv
            baris = []
            for k in self._alat.daftar_kategori():
                baris.append([k])
            self._tulis_file("kategori", ["kategori"], baris)

            # transaksi.csv dan detail_transaksi.csv
            # satu transaksi bisa berisi banyak alat, jadi alatnya ditulis di file detail (satu alat = satu baris)
            baris_transaksi = []
            baris_detail = []
            for t in self._trx.semua():
                baris_transaksi.append([t.id, t.nim, tanggal_ke_teks(t.tanggal_pinjam),
                                        tanggal_ke_teks(t.batas_kembali), t.status])
                for d in t.items.values():
                    kondisi = d.kondisi_kembali
                    if kondisi is None:
                        kondisi = KOSONG
                    terlambat = "0"
                    if d.terlambat:
                        terlambat = "1"
                    baris_detail.append([t.id, d.kode_alat, tanggal_ke_teks(d.tanggal_kembali),
                                         kondisi, terlambat])
            self._tulis_file("transaksi", ["id", "nim", "tanggal_pinjam", "batas_kembali", "status"],
                             baris_transaksi)
            self._tulis_file("detail", ["id_transaksi", "kode_alat", "tanggal_kembali",
                                        "kondisi_kembali", "terlambat"], baris_detail)

            # log.csv
            baris = []
            for e in self._log.semua():
                baris.append([e["waktu"], e["pesan"]])
            self._tulis_file("log", ["waktu", "pesan"], baris)
        except OSError as e:
            raise PenyimpananError(f"Gagal menulis data ke folder '{self._folder}': {e}")

    # ------------------------------------------------------------------ MEMBACA
    def _baca_file(self, kunci, jumlah_kolom):
        """Baca satu file CSV. Hasilnya list berisi (nomor_baris, [kolom, ...]).

        File yang belum ada dianggap data kosong. Baris judul dan baris kosong dilewati."""
        nama = NAMA_FILE[kunci]
        hasil = []
        if not os.path.exists(self._path(kunci)):
            return hasil
        try:
            # utf-8-sig: file dengan maupun tanpa BOM sama-sama terbaca
            with open(self._path(kunci), "r", encoding="utf-8-sig", newline="") as f:
                pembaca = csv.reader(f, delimiter=PEMISAH)
                baris_pertama = True
                for kolom in pembaca:
                    no = pembaca.line_num
                    if "".join(kolom).strip() == "":
                        continue  # baris kosong
                    if baris_pertama:
                        baris_pertama = False
                        if kolom[0].strip().lower() == KOLOM_PERTAMA[kunci]:
                            continue  # ini baris judul kolom, bukan data
                    if len(kolom) != jumlah_kolom:
                        raise PenyimpananError(
                            f"{nama} baris {no}: diharapkan {jumlah_kolom} kolom, ditemukan {len(kolom)}.")
                    hasil.append((no, kolom))
        except OSError as e:
            raise PenyimpananError(f"{nama} tidak dapat dibaca: {e}")
        except UnicodeDecodeError:
            raise PenyimpananError(f"{nama} harus disimpan dengan encoding UTF-8.")
        except csv.Error as e:
            raise PenyimpananError(f"{nama} baris {pembaca.line_num}: format CSV tidak valid ({e}).")
        return hasil

    @staticmethod
    def _salah(nama_file, no, pesan):
        """Buat PenyimpananError yang menyebut nama file dan nomor barisnya."""
        return PenyimpananError(f"{nama_file} baris {no}: {pesan}")

    def muat(self):
        """Isi semua service dari file CSV.

        Bila file rusak atau tidak konsisten, PenyimpananError dilempar dan program dihentikan
        oleh pemanggil (main.py), supaya data lama tidak tertimpa data yang setengah benar."""
        self._muat_log()
        self._muat_mahasiswa()
        self._muat_alat()
        self._muat_transaksi()  # harus terakhir: transaksi memakai data mahasiswa dan alat
        self._cek_konsistensi()

    def _muat_log(self):
        daftar = []
        for no, kolom in self._baca_file("log", 2):
            daftar.append({"waktu": kolom[0], "pesan": kolom[1]})
        self._log.muat(daftar)

    def _muat_mahasiswa(self):
        daftar = []
        nim_terpakai = []
        for no, kolom in self._baca_file("mahasiswa", 3):
            nim = kolom[0]
            nama = kolom[1]
            no_hp = kolom[2]
            if nim == "" or nama == "":
                raise self._salah("mahasiswa.csv", no, "NIM dan nama tidak boleh kosong.")
            if nim in nim_terpakai:
                raise self._salah("mahasiswa.csv", no, f"NIM {nim} muncul lebih dari sekali.")
            nim_terpakai.append(nim)
            daftar.append(Mahasiswa(nim, nama, no_hp))
        self._mhs.muat(daftar)

    def _muat_alat(self):
        daftar = []
        kode_terpakai = []
        for no, kolom in self._baca_file("alat", 5):
            kode = kolom[0]
            nama = kolom[1]
            kategori = kolom[2]
            kondisi = kolom[3]
            status = kolom[4]
            if kode in kode_terpakai:
                raise self._salah("alat.csv", no, f"Kode {kode} muncul lebih dari sekali.")
            if status not in Status_Valid:
                raise self._salah("alat.csv", no, f"Status '{status}' tidak dikenal.")
            try:
                alat = Alat(kode, nama, kategori, kondisi)  # kondisi yang tidak sah ditolak di sini
            except LabError as e:
                raise self._salah("alat.csv", no, str(e))
            # status harus cocok dengan kondisi:
            # alat Tersedia/Dipinjam harus berkondisi Baik; alat Rusak/Pemeliharaan tidak boleh Baik
            kondisi_baik = (kondisi == Kondisi_Baik)
            if (status == Status_Tersedia or status == Status_Dipinjam) and not kondisi_baik:
                raise self._salah("alat.csv", no, f"status '{status}' tidak cocok dengan kondisi '{kondisi}'.")
            if (status == Status_Rusak or status == Status_Pemeliharaan) and kondisi_baik:
                raise self._salah("alat.csv", no, f"status '{status}' tidak cocok dengan kondisi '{kondisi}'.")
            alat.status = status
            kode_terpakai.append(kode)
            daftar.append(alat)

        daftar_kategori = []
        for no, kolom in self._baca_file("kategori", 1):
            daftar_kategori.append(kolom[0])
        self._alat.muat(daftar, daftar_kategori)

    def _muat_transaksi(self):
        # langkah 1: baca transaksi.csv ke dict {id: data}
        data_trx = {}
        for no, kolom in self._baca_file("transaksi", 5):
            id_trx = kolom[0]
            nim = kolom[1]
            tgl_pinjam = kolom[2]
            batas = kolom[3]
            status = kolom[4]
            if id_trx in data_trx:
                raise self._salah("transaksi.csv", no, f"ID {id_trx} muncul lebih dari sekali.")
            if status not in status_valid:
                raise self._salah("transaksi.csv", no, f"Status '{status}' tidak dikenal.")
            try:
                tanggal_pinjam = date.fromisoformat(tgl_pinjam)
                batas_kembali = date.fromisoformat(batas)
            except ValueError:
                raise self._salah("transaksi.csv", no, "Tanggal harus berformat YYYY-MM-DD.")
            data_trx[id_trx] = {"nim": nim, "pinjam": tanggal_pinjam, "batas": batas_kembali,
                                "status": status, "detail": []}

        # langkah 2: baca detail_transaksi.csv, tempelkan tiap baris ke transaksi induknya
        for no, kolom in self._baca_file("detail", 5):
            id_trx = kolom[0]
            kode = kolom[1]
            tgl_kembali = kolom[2]
            kondisi = kolom[3]
            terlambat = kolom[4]
            if id_trx not in data_trx:
                raise self._salah("detail_transaksi.csv", no, f"Transaksi {id_trx} tidak ada di transaksi.csv.")
            if terlambat != "0" and terlambat != "1":
                raise self._salah("detail_transaksi.csv", no, "Kolom terlambat harus 0 atau 1.")
            try:
                tanggal = teks_ke_tanggal(tgl_kembali)
            except ValueError:
                raise self._salah("detail_transaksi.csv", no, "Tanggal harus berformat YYYY-MM-DD atau '-'.")
            if kondisi == KOSONG:
                kondisi = None
            if (tanggal is None and kondisi is not None) or (tanggal is not None and kondisi is None):
                raise self._salah("detail_transaksi.csv", no,
                                  "tanggal_kembali dan kondisi_kembali harus sama-sama terisi atau sama-sama '-'.")
            if kondisi is not None and kondisi not in Kondisi_Valid:
                raise self._salah("detail_transaksi.csv", no, f"kondisi '{kondisi}' tidak dikenal.")
            data_trx[id_trx]["detail"].append({"kode": kode, "tanggal": tanggal, "kondisi": kondisi,
                                               "terlambat": (terlambat == "1")})

        # langkah 3: periksa tiap transaksi lalu ubah menjadi objek Transaksi
        daftar = []
        for id_trx in data_trx:
            d = data_trx[id_trx]
            detail_list = d["detail"]
            if len(detail_list) == 0:
                raise PenyimpananError(f"Transaksi {id_trx} tidak memiliki alat di detail_transaksi.csv.")

            kodes = []
            sudah_kembali = 0
            for item in detail_list:
                kodes.append(item["kode"])
                if item["tanggal"] is not None:
                    sudah_kembali = sudah_kembali + 1
            for kode in kodes:
                if kodes.count(kode) > 1:
                    raise PenyimpananError(f"Transaksi {id_trx}: ada kode alat yang tercatat dua kali.")

            # status transaksi dihitung ulang dari detail, lalu dibandingkan dengan yang tertulis di file
            if sudah_kembali == len(kodes):
                harapan = status_selesai
            elif sudah_kembali == 0:
                harapan = status_dipinjam
            else:
                harapan = status_sebagian
            if d["status"] != harapan:
                raise PenyimpananError(
                    f"Transaksi {id_trx}: status '{d['status']}' tidak sesuai dengan detail alat "
                    f"(seharusnya '{harapan}').")

            trx = Transaksi(id_trx, d["nim"], kodes, d["pinjam"])
            trx.batas_kembali = d["batas"]
            trx.status = d["status"]
            for item in detail_list:
                detail = trx.items[item["kode"]]
                detail.tanggal_kembali = item["tanggal"]
                detail.kondisi_kembali = item["kondisi"]
                detail.terlambat = item["terlambat"]
            daftar.append(trx)

        try:
            self._trx.muat(daftar)
        except LabError as e:
            raise PenyimpananError(f"Data tidak konsisten: {e}")

    def _cek_konsistensi(self):
        """Pastikan status alat sesuai dengan transaksi aktif."""
        # 1. satu alat yang belum kembali hanya boleh ada di satu transaksi aktif
        pemakai = {}  # {kode alat: [id transaksi yang masih memakainya]}
        for trx in self._trx.aktif():
            for kode in trx.belum_kembali():
                if kode not in pemakai:
                    pemakai[kode] = []
                pemakai[kode].append(trx.id)
        for kode in pemakai:
            ids = pemakai[kode]
            if len(ids) > 1:
                raise PenyimpananError(
                    f"Alat {kode} belum dikembalikan di lebih dari satu transaksi aktif ({', '.join(ids)}).")

        # 2. alat berstatus Dipinjam harus tercatat di sebuah transaksi aktif
        for alat in self._alat.semua():
            if alat.status == Status_Dipinjam and len(alat.transaksi_aktif) == 0:
                raise PenyimpananError(
                    f"Alat {alat.kode} berstatus Dipinjam tetapi tidak ada transaksi aktif yang mencatatnya.")

        # 3. alat yang belum kembali di transaksi aktif harus berstatus Dipinjam
        for trx in self._trx.aktif():
            for kode in trx.belum_kembali():
                if self._alat.ambil(kode).status != Status_Dipinjam:
                    raise PenyimpananError(
                        f"Transaksi {trx.id}: alat {kode} belum dikembalikan tetapi statusnya bukan Dipinjam.")
