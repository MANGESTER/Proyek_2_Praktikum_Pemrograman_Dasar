from models.exceptions import DataSudahAdaError

DATA_MAHASISWA = [("M001", "Dika", "081234567890"), ("M002", "Abyan", "081234567891"),
                  ("M003", "Ayun", "081234567892"), ("M004", "Adibah", "081234567893")]
DATA_ALAT = [("A001", "Laptop", "perangkat komputasi"), ("A002", "Raspberry Pi", "perangkat komputasi"),
             ("A003", "Router", "perangkat jaringan"), ("A004", "Kabel LAN", "perangkat jaringan"),
             ("A005", "Kamera Digital", "perangkat multimedia"), ("A006", "Tripod", "perangkat multimedia"),
             ("A007", "Multimeter", "perangkat elektronik"), ("A008", "Multimeter", "perangkat elektronik")]


def muat_data_contoh(mhs, alat):
    # periksa dulu: data contoh dimuat seluruhnya atau tidak sama sekali (tidak setengah jalan)
    nim_ada = {m.nim for m in mhs.semua()}
    kode_ada = {a.kode for a in alat.semua()}
    bentrok = [n for n, _, _ in DATA_MAHASISWA if n in nim_ada] + [k for k, _, _ in DATA_ALAT if k in kode_ada]
    if bentrok:
        raise DataSudahAdaError("Data contoh tidak dimuat karena sudah ada: " + ", ".join(bentrok)
                                + ". Hapus data tersebut atau mulai dari folder data/ yang kosong.")
    for nim, nama, hp in DATA_MAHASISWA:
        mhs.tambah(nim, nama, hp)
    for kode, nama, kat in DATA_ALAT:
        alat.tambah(kode, nama, kat)
