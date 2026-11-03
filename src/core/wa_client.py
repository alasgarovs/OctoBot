"""The only module that knows about neonize. No Qt imports here.

If the library changes, only this file has to change.

Callbacks (called from library threads - never touch UI objects in them):
    on_qr(text)               a QR payload to render and scan
    on_status(state, detail)  state: connecting | connected | disconnected |
                              logged_out | paired | error | phone
"""

import gc
import sqlite3
import threading
import time

from core.paths import SESSION_PATH, delete_session


class WhatsAppClient:
    def __init__(self, on_qr=None, on_status=None):
        self._on_qr = on_qr or (lambda text: None)
        self._on_status = on_status or (lambda state, detail="": None)
        self._client = None
        self._build_jid = None
        self._connected = threading.Event()
        self._lock = threading.Lock()
        self._logout_in_progress = False

    # ------------------------------------------------------------ state
    @property
    def is_connected(self):
        return self._connected.is_set()

    def wait_connected(self, timeout):
        return self._connected.wait(timeout)

    def _status(self, state, detail=""):
        try:
            self._on_status(state, detail)
        except Exception:
            pass

    # ------------------------------------------------------- connect/stop
    def start(self):
        """Create the client and connect in a background thread (non-blocking)."""
        stored = stored_phone()
        if stored:
            # The saved login already tells us which account this is.
            self._status("phone", stored)
        with self._lock:
            if self._client is not None:
                return

            try:
                from neonize.client import NewClient
                from neonize.events import (ConnectedEv, DisconnectedEv,
                                            LoggedOutEv, PairStatusEv)
                from neonize.utils import build_jid
            except Exception as e:  # missing/broken install
                self._status("error", f"neonize import failed: {e}")
                return

            self._build_jid = build_jid
            try:
                client = NewClient(str(SESSION_PATH))
            except Exception as e:
                self._status("error", f"NewClient failed: {e}")
                return

            @client.event(ConnectedEv)
            def _on_connected(client, _event):
                self._connected.set()
                self._status("connected")
                # Ask for the account's own number off the event thread:
                # client calls are blocking RPCs.
                threading.Thread(target=self._report_phone, args=(client,),
                                 daemon=True, name="octobot-wa-me").start()

            @client.event(DisconnectedEv)
            def _on_disconnected(_client, _event):
                self._connected.clear()
                self._status("disconnected")

            @client.event(LoggedOutEv)
            def _on_logged_out(_client, _event):
                self._connected.clear()
                if self._logout_in_progress:
                    return  # logout() tears down and wipes by itself
                threading.Thread(target=self._server_logout_wipe, daemon=True,
                                 name="octobot-wa-wipe").start()

            @client.event(PairStatusEv)
            def _on_pair(_client, _event):
                self._status("paired")

            # Custom QR callback: the payload is rendered in our own dialog.
            # (If this hook is unavailable in the installed version, the library
            # falls back to printing the QR in the terminal.)
            try:
                client.qr(self._handle_qr)
            except Exception as e:
                self._status("error", f"QR hook not available: {e}")

            self._client = client

        self._status("connecting")
        threading.Thread(target=self._run, args=(client,), daemon=True,
                         name="octobot-wa").start()

    def _run(self, client):
        try:
            client.connect()
        except Exception as e:
            self._connected.clear()
            self._status("error", str(e))

    def _handle_qr(self, _client, data):
        if isinstance(data, (list, tuple)):
            data = data[0]
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        self._on_qr(str(data))

    def _report_phone(self, client):
        """Tell the UI which account just connected (state 'phone')."""
        phone = _connected_phone(client)
        if phone:
            self._status("phone", phone)

    def _release(self, client):
        """Fully stop a neonize client and force the Go runtime to release
        its resources.

        The Go-side store (which holds the open SQLite session file) is only
        freed when the Python wrapper object is garbage-collected
        (neonize releases it via weakref.finalize). Deliberately dropping the
        reference before deleting the session files makes delete_session()
        actually succeed instead of failing on a locked file.
        """
        for method in ("stop", "disconnect"):
            try:
                getattr(client, method)()
            except Exception:
                pass
        del client
        gc.collect()

    def stop(self):
        """Disconnect but keep the saved login."""
        with self._lock:
            client, self._client = self._client, None
        self._connected.clear()
        if client is not None:
            self._release(client)

    def logout(self):
        """Unlink this device and wipe the saved login from disk."""
        self._logout_in_progress = True
        with self._lock:
            client, self._client = self._client, None
        self._connected.clear()
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass
            self._release(client)
        time.sleep(0.5)  # give the runtime a beat to settle before wiping
        wiped = delete_session()
        self._logout_in_progress = False
        return wiped

    def _server_logout_wipe(self):
        """The server unlinked this device: tear down and wipe the session."""
        with self._lock:
            client, self._client = self._client, None
        self._connected.clear()
        if client is not None:
            self._release(client)
            time.sleep(0.5)  # give the runtime a beat to settle before wiping
        wiped = delete_session()
        self._status("logged_out", "wiped" if wiped else "left")

    # ---------------------------------------------------------- actions
    def check_numbers(self, numbers):
        """Return {number: bool} for the numbers WhatsApp answered about.

        Numbers missing from the result were not reported by the server.
        """
        client = self._require_client()
        queries = [f"+{n}" for n in numbers]

        try:
            responses = client.is_on_whatsapp(queries)
        except TypeError:
            responses = client.is_on_whatsapp(*queries)

        result = {}
        for position, item in enumerate(responses or []):
            is_in = _first_attr(item, ("IsIn", "is_in"), False)
            query = _first_attr(item, ("Query", "query"), "")
            key = str(query).lstrip("+") if query else None
            if key is None and len(responses) == len(numbers):
                key = numbers[position]
            if key:
                result[key] = bool(is_in)
        return result

    def send_text(self, number, text):
        client = self._require_client()
        jid = self._build_jid(number)
        client.send_message(jid, text)

    def _require_client(self):
        client = self._client
        if client is None or not self._connected.is_set():
            raise ConnectionError("WhatsApp is not connected")
        return client


def _first_attr(obj, names, default):
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _connected_phone(client):
    """The account's own number from get_me(), '' when unavailable."""
    try:
        user = client.get_me().JID.User
    except Exception:
        return ""
    return str(user or "").strip()


def stored_phone():
    """The number of the account saved in the session DB, '' when unknown.

    whatsmeow keeps the device JID in its whatsmeow_device table, so the
    number is available even before the client connects. immutable=1 reads
    a WAL database without locks, safe while the client is running.
    """
    try:
        conn = sqlite3.connect(f"file:{SESSION_PATH}?immutable=1", uri=True)
        try:
            row = conn.execute("SELECT jid FROM whatsmeow_device LIMIT 1").fetchone()
        finally:
            conn.close()
    except Exception:
        return ""
    if not row or not row[0]:
        return ""
    return str(row[0]).split(":", 1)[0].split("@", 1)[0]
