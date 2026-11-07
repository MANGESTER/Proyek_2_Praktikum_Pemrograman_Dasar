class LabError(Exception):
    'Ada Kesalahan Aplikasi'

class ValidasiError(LabError):
    'Input tidak valid'

class DataTidakDitemukanError(LabError):
    'Data yang dicari tidak ditemukan'

class DataSudahAdaError(LabError):
    'Data sudah ada atau sudah terdafar'

class AturanBisnisError(LabError):
    'Operasi melanggar aturan bisnis laboratorium'

class PenyimpananError(LabError):
    'Gagal membaca atau menulis file data (.txt)'
