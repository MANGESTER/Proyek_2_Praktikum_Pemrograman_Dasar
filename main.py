import os
import sys

from models.exceptions import PenyimpananError
from services.alat_service import AlatService
from services.log_service import LogService
from services.mahasiswa_service import MahasiswaService
from services.penyimpanan_csv_service import PenyimpananCsv
from services.statistik_service import StatistikService
from services.transaksi_service import TransaksiService
from ui.menu import MenuCLI

# Folder data selalu berada di sebelah main.py, apa pun folder tempat program dijalankan.
FOLDER_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def main():
    log = LogService()
    mahasiswa = MahasiswaService(log)
    alat = AlatService(log)
    transaksi = TransaksiService(mahasiswa, alat, log)
    statistik = StatistikService(transaksi)
    penyimpanan = PenyimpananCsv(FOLDER_DATA, log, mahasiswa, alat, transaksi)

    try:
        penyimpanan.muat()
    except PenyimpananError as e:
        print(f"[!] Data tersimpan tidak dapat dibaca: {e}")
        print("    Program dihentikan agar data lama tidak tertimpa.")
        print(f"    Perbaiki file di folder '{FOLDER_DATA}', atau hapus folder itu untuk mulai dari awal.")
        sys.exit(1)

    print(f"Data dimuat dari '{FOLDER_DATA}': {len(mahasiswa.semua())} mahasiswa, "
          f"{len(alat.semua())} alat, {len(transaksi.semua())} transaksi.")
    try:
        MenuCLI(mahasiswa, alat, transaksi, statistik, log, penyimpanan).jalan()
    except (KeyboardInterrupt, EOFError):  # Ctrl+C atau Ctrl+Z/Ctrl+D di prompt
        print("\nProgram dihentikan. Menyimpan data...")
        try:
            penyimpanan.simpan()
        except PenyimpananError as e:
            print(f"[!] PERINGATAN: data belum tersimpan ke file. {e}")

if __name__ == "__main__":
    main()
