"""User-data locations. Never write next to the exe: that folder is often read-only."""

import sys
import time
from pathlib import Path

from platformdirs import user_data_dir

APP_DIR_NAME = "OctoBot"

DATA_DIR = Path(user_data_dir(APP_DIR_NAME, appauthor=False))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "local.db"

# neonize/whatsmeow keeps the WhatsApp login (device keys) in this SQLite file.
SESSION_PATH = DATA_DIR / "whatsapp_session.db"


def resource_dir(name):
    """Location of a bundled read-only resource folder (dev or frozen exe).

    'translations' sits beside the app package in development and 'icons' in
    the repository root; a frozen build places both at the bundle root
    (--add-data), where sys._MEIPASS points.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / name
    here = Path(__file__).resolve().parent          # .../src/core
    if name == "translations":
        return here.parent / name                   # .../src/translations
    return here.parent.parent / name                # <repo>/icons


def session_files():
    """The session file plus SQLite side files (WAL mode)."""
    return [SESSION_PATH, SESSION_PATH.with_name(SESSION_PATH.name + "-wal"),
            SESSION_PATH.with_name(SESSION_PATH.name + "-shm")]


def has_session():
    return SESSION_PATH.exists()


def delete_session(attempts=10, delay=0.6):
    """Remove the session files for good.

    The client may recreate them while shutting down, so keep deleting
    until they stay gone. True when the WhatsApp data is fully wiped.
    """
    for _ in range(attempts):
        for path in session_files():
            try:
                path.unlink()
            except OSError:
                pass
        time.sleep(delay)
        if not any(path.exists() for path in session_files()):
            return True
    return False
