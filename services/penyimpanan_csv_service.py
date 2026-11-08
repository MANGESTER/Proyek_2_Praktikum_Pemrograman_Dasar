"""Penyimpanan permanen ke file .csv (Proyek 2, versi CSV).

Setiap jenis data disimpan di satu file CSV. Baris pertama berisi nama kolom, baris berikutnya berisi data.
Pemisah kolom adalah ';' (cocok dengan Excel berbahasa Indonesia); ubah PEMISAH menjadi ',' bila perlu.
Saat membaca, pemisah ';' maupun ',' dikenali otomatis.

    data/mahasiswa.csv         nim;nama;no_hp
    data/alat.csv              kode;nama;kategori;kondisi;status
    data/kategori.csv          kategori
    data/transaksi.csv         id;nim;tanggal_pinjam;batas_kembali;status
    data/detail_transaksi.csv  id_transaksi;kode_alat;tanggal_kembali;kondisi_kembali;terlambat
    data/log.csv               waktu;pesan

Status "aktif" mahasiswa dan alat TIDAK disimpan; dihitung ulang dari transaksi saat file dimuat,
sehingga tidak mungkin berbeda dengan isi transaksi.
"""
import csv
import io
import os
import shutil
import re
from datetime import date

from models.alat import (Alat, Kondisi_Baik, Kondisi_Valid, Status_Dipinjam, Status_Pemeliharaan,
                         Status_Rusak, Status_Tersedia, Status_Valid)
from models.exceptions import LabError, PenyimpananError
from models.mahasiswa import Mahasiswa
from models.transaksi import Transaksi, status_dipinjam, status_sebagian, status_selesai, status_valid

KOSONG = "-"  # penanda nilai kosong (mis. tanggal kembali alat yang belum dikembalikan)
PEMISAH = ","  # pemisah kolom saat menulis

NAMA_FILE = {
    "mahasiswa": "mahasiswa.csv",
    "alat": "alat.csv",
    "kategori": "kategori.csv",
    "transaksi": "transaksi.csv",
    "detail": "detail_transaksi.csv",
    "log": "log.csv",
}
# nama kolom pertama tiap file; dipakai untuk mengenali (dan melewati) baris judul
KOLOM_PERTAMA = {"mahasiswa": "nim", "alat": "kode", "kategori": "kategori",
                 "transaksi": "id", "detail": "id_transaksi", "log": "waktu"}


def _tanggal_ke_teks(nilai):
    return nilai.isoformat() if nilai else KOSONG


def _teks_ke_tanggal(teks):
    return None if teks == KOSONG else date.fromisoformat(teks)


def _deteksi_pemisah(teks):
    """Pilih ';' atau ',' berdasarkan baris pertama (isi di dalam tanda kutip diabaikan)."""
    for baris in teks.splitlines():
        if baris.strip():
            polos = re.sub(r'"(?:[^"]|"")*"', "", baris)
            titik_koma, koma = polos.count(";"), polos.count(",")
            return ";" if titik_koma > koma else ("," if koma > titik_koma else PEMISAH)
    return PEMISAH


class PenyimpananCsv:
    """Membaca (muat) dan menulis (simpan) seluruh data aplikasi ke folder berisi file .csv."""

    def __init__(self, folder, log, mahasiswa_service, alat_service, transaksi_service):
        self._folder = folder
        self._log = log
        self._mhs = mahasiswa_service
        self._alat = alat_service
        self._trx = transaksi_service
        self._terakhir = {}  # isi terakhir yang dimuat/ditulis per file, agar file yang tak berubah tidak ditulis ulang

    @property
    def folder(self):
        return self._folder

    def _path(self, kunci):
        return os.path.join(self._folder, NAMA_FILE[kunci])

    # ------------------------------------------------------------------ menulis
    def _bangun(self):
        """Susun isi teks setiap file dari keadaan data saat ini."""
        isi = {
            "mahasiswa": ("nim|nama|no_hp",
                          [[m.nim, m.nama, m.no_hp] for m in self._mhs.semua()]),
            "alat": ("kode|nama|kategori|kondisi|status",
                     [[a.kode, a.nama, a.kategori, a.kondisi, a.status] for a in self._alat.semua()]),
            "kategori": ("kategori", [[k] for k in self._alat.daftar_kategori()]),
            "transaksi": ("id|nim|tanggal_pinjam|batas_kembali|status",
                          [[t.id, t.nim, _tanggal_ke_teks(t.tanggal_pinjam),
                            _tanggal_ke_teks(t.batas_kembali), t.status]
                           for t in self._trx.semua()]),
            "detail": ("id_transaksi|kode_alat|tanggal_kembali|kondisi_kembali|terlambat",
                       [[t.id, d.kode_alat, _tanggal_ke_teks(d.tanggal_kembali),
                         d.kondisi_kembali or KOSONG, "1" if d.terlambat else "0"]
                        for t in self._trx.semua() for d in t.items.values()]),
            "log": ("waktu|pesan", [[e["waktu"], e["pesan"]] for e in self._log.semua()]),
        }
        hasil = {}
        for kunci, (judul, baris) in isi.items():
            buf = io.StringIO()
            tulis = csv.writer(buf, delimiter=PEMISAH, lineterminator="\r\n")
            tulis.writerow(judul.split("|"))  # baris pertama = nama kolom
            tulis.writerows(baris)  # modul csv memberi tanda kutip otomatis bila perlu
            hasil[kunci] = buf.getvalue()
        return hasil

    @staticmethod
    def _hapus_sisa(daftar):
        """Hapus file sementara/cadangan bila ada (kegagalan menghapus diabaikan)."""
        for path in daftar:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def simpan(self):
        """Tulis file yang isinya berubah. Semua file ditulis ke *.tmp dulu, baru diganti sekaligus."""
        baru = self._bangun()
        berubah = [k for k, teks in baru.items()
                   if teks != self._terakhir.get(k) or not os.path.exists(self._path(k))]
        if not berubah:
            return
        sementara = []  # (file sementara, file tujuan)
        cadangan = {}  # file tujuan -> salinan isi lama (.bak), untuk membatalkan bila penggantian gagal di tengah
        diganti = []  # file tujuan yang sudah berhasil diganti
        try:
            os.makedirs(self._folder, exist_ok=True)
            for kunci in berubah:
                path = self._path(kunci)
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8-sig", newline="") as f:  # -sig: Excel mengenali UTF-8
                    f.write(baru[kunci])
                sementara.append((tmp, path))
            for _, path in sementara:
                if os.path.exists(path):
                    shutil.copyfile(path, path + ".bak")
                    cadangan[path] = path + ".bak"
            for tmp, path in sementara:
                os.replace(tmp, path)
                diganti.append(path)
        except OSError as e:
            # penggantian gagal di tengah (mis. file dikunci OneDrive): kembalikan yang sudah terlanjur diganti
            # supaya file di disk tetap sinkron satu sama lain
            for path in reversed(diganti):
                try:
                    if path in cadangan:
                        os.replace(cadangan.pop(path), path)
                    else:
                        os.remove(path)
                except OSError:
                    pass
            self._hapus_sisa([tmp for tmp, _ in sementara] + list(cadangan.values()))
            raise PenyimpananError(f"Gagal menulis data ke folder '{self._folder}': {e}")
        self._hapus_sisa(list(cadangan.values()))
        self._terakhir.update({k: baru[k] for k in berubah})

    # ------------------------------------------------------------------ membaca
    def _baca(self, kunci, jumlah_kolom):
        """Kembalikan list (nomor_baris, [kolom...]). File belum ada = data kosong."""
        path = self._path(kunci)
        nama = NAMA_FILE[kunci]
        if not os.path.exists(path):
            return []
        try:
            with open(path, "rb") as f:
                mentah = f.read()
        except OSError as e:
            raise PenyimpananError(f"{nama} tidak dapat dibaca: {e}")
        try:
            teks = mentah.decode("utf-8-sig")  # -sig: abaikan BOM
        except UnicodeDecodeError:
            teks = mentah.decode("cp1252", errors="replace")  # CSV hasil simpan Excel biasa (bukan 'CSV UTF-8')
        pembaca = csv.reader(io.StringIO(teks, newline=""), delimiter=_deteksi_pemisah(teks))
        hasil, judul_dilewati = [], False
        try:
            for kolom in pembaca:
                no = pembaca.line_num
                while len(kolom) > jumlah_kolom and kolom[-1].strip() == "":
                    kolom.pop()  # Excel sering menambah kolom kosong di ujung baris
                if not any(k.strip() for k in kolom):
                    continue  # baris kosong
                if not judul_dilewati:
                    judul_dilewati = True
                    if kolom[0].strip().lower() == KOLOM_PERTAMA[kunci]:
                        continue  # baris judul kolom
                if len(kolom) != jumlah_kolom:
                    raise PenyimpananError(
                        f"{nama} baris {no}: diharapkan {jumlah_kolom} kolom, ditemukan {len(kolom)}.")
                hasil.append((no, kolom))
        except csv.Error as e:
            raise PenyimpananError(f"{nama} baris {pembaca.line_num}: format CSV tidak valid ({e}).")
        return hasil

    @staticmethod
    def _bungkus(nama_file, no, kesalahan):
        return PenyimpananError(f"{nama_file} baris {no}: {kesalahan}")

    def muat(self):
        """Isi semua service dari file. Bila file rusak/tidak konsisten, PenyimpananError dilempar
        dan data di memori tidak boleh dipakai (pemanggil menghentikan program)."""
        # 1. log
        self._log.muat([{"waktu": w, "pesan": p} for _, (w, p) in self._baca("log", 2)])

        # 2. mahasiswa
        daftar_mhs = {}
        for no, (nim, nama, hp) in self._baca("mahasiswa", 3):
            if not nim or not nama:
                raise self._bungkus("mahasiswa.csv", no, "NIM dan nama tidak boleh kosong.")
            if nim in daftar_mhs:
                raise self._bungkus("mahasiswa.csv", no, f"NIM {nim} muncul lebih dari sekali.")
            daftar_mhs[nim] = Mahasiswa(nim, nama, hp)
        self._mhs.muat(daftar_mhs.values())

        # 3. alat
        daftar_alat = {}
        for no, (kode, nama, kategori, kondisi, status) in self._baca("alat", 5):
            if kode in daftar_alat:
                raise self._bungkus("alat.csv", no, f"Kode {kode} muncul lebih dari sekali.")
            if status not in Status_Valid:
                raise self._bungkus("alat.csv", no, f"Status '{status}' tidak dikenal.")
            try:
                alat = Alat(kode, nama, kategori, kondisi)
            except LabError as e:
                raise self._bungkus("alat.csv", no, str(e))
            baik = kondisi == Kondisi_Baik
            if (status in (Status_Tersedia, Status_Dipinjam) and not baik) or \
                    (status in (Status_Rusak, Status_Pemeliharaan) and baik):
                raise self._bungkus("alat.csv", no, f"status '{status}' tidak cocok dengan kondisi '{kondisi}'.")
            alat.status = status
            daftar_alat[kode] = alat
        kategori = [k for _, (k,) in self._baca("kategori", 1)]
        self._alat.muat(daftar_alat.values(), kategori)

        # 4. transaksi + detailnya
        daftar_trx = {}
        for no, (id_trx, nim, tgl_pinjam, batas, status) in self._baca("transaksi", 5):
            if id_trx in daftar_trx:
                raise self._bungkus("transaksi.csv", no, f"ID {id_trx} muncul lebih dari sekali.")
            if status not in status_valid:
                raise self._bungkus("transaksi.csv", no, f"Status '{status}' tidak dikenal.")
            try:
                daftar_trx[id_trx] = {"nim": nim, "pinjam": date.fromisoformat(tgl_pinjam),
                                      "batas": date.fromisoformat(batas), "status": status, "detail": []}
            except ValueError:
                raise self._bungkus("transaksi.csv", no, "Tanggal harus berformat YYYY-MM-DD.")
        for no, (id_trx, kode, tgl_kembali, kondisi, terlambat) in self._baca("detail", 5):
            if id_trx not in daftar_trx:
                raise self._bungkus("detail_transaksi.csv", no, f"Transaksi {id_trx} tidak ada di transaksi.csv.")
            if terlambat not in ("0", "1"):
                raise self._bungkus("detail_transaksi.csv", no, "Kolom terlambat harus 0 atau 1.")
            try:
                tgl = _teks_ke_tanggal(tgl_kembali)
            except ValueError:
                raise self._bungkus("detail_transaksi.csv", no, "Tanggal harus berformat YYYY-MM-DD atau '-'.")
            kondisi_nilai = None if kondisi == KOSONG else kondisi
            if (tgl is None) != (kondisi_nilai is None):
                raise self._bungkus("detail_transaksi.csv", no,
                                    "tanggal_kembali dan kondisi_kembali harus sama-sama terisi atau sama-sama '-'.")
            if kondisi_nilai is not None and kondisi_nilai not in Kondisi_Valid:
                raise self._bungkus("detail_transaksi.csv", no, f"kondisi '{kondisi_nilai}' tidak dikenal.")
            daftar_trx[id_trx]["detail"].append((no, kode, tgl, kondisi_nilai, terlambat == "1"))

        hasil = []
        for id_trx, d in daftar_trx.items():
            if not d["detail"]:
                raise PenyimpananError(f"Transaksi {id_trx} tidak memiliki alat di detail_transaksi.csv.")
            kodes = [kode for _, kode, _, _, _ in d["detail"]]
            if len(set(kodes)) != len(kodes):
                raise PenyimpananError(f"Transaksi {id_trx}: ada kode alat yang tercatat dua kali.")
            kembali = sum(1 for _, _, tgl, _, _ in d["detail"] if tgl is not None)
            harapan = status_selesai if kembali == len(kodes) else (status_dipinjam if kembali == 0 else status_sebagian)
            if d["status"] != harapan:
                raise PenyimpananError(
                    f"Transaksi {id_trx}: status '{d['status']}' tidak sesuai dengan detail alat (seharusnya '{harapan}').")
            trx = Transaksi(id_trx, d["nim"], kodes, d["pinjam"])
            trx.batas_kembali = d["batas"]
            trx.status = d["status"]
            for no, kode, tgl, kondisi, terlambat in d["detail"]:
                detail = trx.items[kode]
                detail.tanggal_kembali = tgl
                detail.kondisi_kembali = kondisi
                detail.terlambat = terlambat
            hasil.append(trx)

        try:
            self._trx.muat(hasil)
        except LabError as e:
            raise PenyimpananError(f"Data tidak konsisten: {e}")
        self._cek_konsistensi()
        self._terakhir = self._bangun()

    def _cek_konsistensi(self):
        """Pastikan status alat sesuai dengan transaksi aktif."""
        pemakai = {}
        for trx in self._trx.aktif():
            for kode in trx.belum_kembali():
                pemakai.setdefault(kode, []).append(trx.id)
        for kode, ids in pemakai.items():
            if len(ids) > 1:
                raise PenyimpananError(
                    f"Alat {kode} belum dikembalikan di lebih dari satu transaksi aktif ({', '.join(ids)}).")
        for alat in self._alat.semua():
            if alat.status == Status_Dipinjam and not alat.transaksi_aktif:
                raise PenyimpananError(
                    f"Alat {alat.kode} berstatus Dipinjam tetapi tidak ada transaksi aktif yang mencatatnya.")
        for trx in self._trx.aktif():
            for kode in trx.belum_kembali():
                if self._alat.ambil(kode).status != Status_Dipinjam:
                    raise PenyimpananError(
                        f"Transaksi {trx.id}: alat {kode} belum dikembalikan tetapi statusnya bukan Dipinjam.")
