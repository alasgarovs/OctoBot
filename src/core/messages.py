"""Message templates: CRUD plus the active selection. No Qt imports here.

Exactly one template is active at a time and the campaign sends its text.
Blank titles are auto-numbered so a template is never unnamed.
"""

from core.db import Message, Session

MAX_TITLE = 100
MAX_TEXT = 10000


def list_messages():
    """All templates, oldest first: [{id, title, message, is_active}]."""
    with Session() as session:
        rows = session.query(Message).order_by(Message.id).all()
        return [{"id": row.id, "title": row.title, "message": row.message,
                 "is_active": bool(row.is_active)} for row in rows]


def get_active():
    """The active template as a dict, or None when there is none."""
    with Session() as session:
        row = session.query(Message).filter(Message.is_active).order_by(Message.id).first()
        if row is None:
            return None
        return {"id": row.id, "title": row.title, "message": row.message}


def get_active_text():
    """The text of the active template, or ''."""
    template = get_active()
    return template["message"] if template else ""


def create_message(title, text):
    """Insert a template and return its id."""
    with Session() as session:
        row = Message(title=_auto_title(session, title), message=(text or "")[:MAX_TEXT])
        session.add(row)
        session.flush()
        row_id = row.id
        session.commit()
        return row_id


def update_message(message_id, title, text):
    """Overwrite a template's title and text. False when it does not exist."""
    with Session() as session:
        row = session.get(Message, message_id)
        if row is None:
            return False
        row.title = _auto_title(session, title)
        row.message = (text or "")[:MAX_TEXT]
        session.commit()
        return True


def delete_message(message_id):
    """Remove a template. Deleting the active one leaves none active."""
    with Session() as session:
        row = session.get(Message, message_id)
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True


def set_active(message_id):
    """Make this template the one the campaign sends."""
    with Session() as session:
        row = session.get(Message, message_id)
        if row is None:
            return False
        session.query(Message).filter(Message.id != message_id, Message.is_active).update(
            {"is_active": False}, synchronize_session=False)
        row.is_active = True
        session.commit()
        return True


def _auto_title(session, title):
    """A non-empty unique title; blank ones become 'Message N'."""
    title = (title or "").strip()[:MAX_TITLE]
    if title:
        return title
    existing = {row.title for row in session.query(Message.title)}
    number = len(existing) + 1
    while f"Message {number}" in existing:
        number += 1
    return f"Message {number}"
