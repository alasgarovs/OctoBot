import sys
from pathlib import Path


def _read_version():
    if getattr(sys, "frozen", False):
        path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "VERSION"
    else:
        path = Path(__file__).resolve().parent.parent / "VERSION"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


app_version = _read_version() or "0.0.0.0"
app_name = 'OctoBot'
original_filename = 'OctoBot.exe'
file_description = 'WhatsApp Messaging Bot'
company_name = 'Alasgarovs'
legal_copyright = 'All Rights Reserved © 2026.'
