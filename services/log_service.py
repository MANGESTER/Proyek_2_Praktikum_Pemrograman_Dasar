from datetime import datetime


class LogService:
    """Tantangan D: log aktivitas disimpan dalam list of dict."""

    def __init__(self):
        self._entries = []

    def catat(self, pesan):
        self._entries.append({"waktu": datetime.now().strftime("%Y-%m-%d %H:%M"), "pesan": pesan})

    def muat(self, entries):
        """Ganti isi log dengan data dari file (tanpa mencatat log baru)."""
        self._entries = list(entries)

    def semua(self):
        return list(self._entries)

    def format_baris(self):
        return [f"[{e['waktu']}] {e['pesan']}" for e in self._entries]
