from models.exceptions import ValidasiError


def wajib(nilai, label):
    """Pastikan teks tidak kosong; kembalikan teks yang sudah di-strip."""
    nilai = (nilai or "").strip()
    if not nilai:
        raise ValidasiError(f"{label} tidak boleh kosong.")
    return nilai
