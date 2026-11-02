"""Sending service. No Qt imports here.

Flow: drop already-used numbers -> check which numbers are on WhatsApp (batches)
-> send to the rest. After every number the result is written to Pool and the
number leaves the queue in one transaction, so no number is ever lost.

emit(key, args) keys:
    not_connected, queue_empty, already_used(n), checking(done, total),
    check_failed(error), not_on_whatsapp(n), sent(n), failed(n, error),
    daily_limit(limit), connection_lost, stopped, completed

run_campaign returns the end reason:
    completed | stopped | connection_lost | daily_limit | queue_empty | not_connected
"""

import random
import time
from datetime import datetime, timezone

from core.db import (Pool, Session, STATUS_FAILED, STATUS_NOT_ON_WHATSAPP,
                     STATUS_SENT, TempNumbers, get_settings, utcnow)

CHECK_BATCH = 50
RECONNECT_WAIT = 30  # seconds to wait for the library's auto-reconnect


def run_campaign(wa, message, emit, counts_changed=None, should_stop=None):
    should_stop = should_stop or (lambda: False)
    counts_changed = counts_changed or (lambda: None)

    if not wa.is_connected:
        emit("not_connected", ())
        return "not_connected"

    settings = get_settings()

    with Session() as session:
        queue = [row.number for row in session.query(TempNumbers).order_by(TempNumbers.id)]
        used = {number for (number,) in session.query(Pool.number)}

    if not queue:
        emit("queue_empty", ())
        return "queue_empty"

    # 1. Numbers that were processed before leave the queue untouched in Pool.
    already = [n for n in queue if n in used]
    for number in already:
        emit("already_used", (number,))
    _remove_from_queue(already)
    pending = [n for n in queue if n not in used]
    counts_changed()

    # 2. Bulk check: who is on WhatsApp at all?
    sendable = []
    for start in range(0, len(pending), CHECK_BATCH):
        if should_stop():
            emit("stopped", ())
            return "stopped"

        batch = pending[start:start + CHECK_BATCH]
        emit("checking", (min(start + len(batch), len(pending)), len(pending)))

        try:
            found = wa.check_numbers(batch)
        except Exception as e:
            if not wa.is_connected and not wa.wait_connected(RECONNECT_WAIT):
                emit("connection_lost", ())
                return "connection_lost"
            emit("check_failed", (e,))
            found = {}  # unknown -> try to send, the send result decides

        for number in batch:
            if found.get(number, True):
                sendable.append(number)
            else:
                _record(number, STATUS_NOT_ON_WHATSAPP)
                emit("not_on_whatsapp", (number,))
        counts_changed()

    # 3. Send.
    limit = settings["daily_limit"]
    sent_today = _sent_today() if limit else 0

    for index, number in enumerate(sendable):
        if should_stop():
            emit("stopped", ())
            return "stopped"

        if limit and sent_today >= limit:
            emit("daily_limit", (limit,))
            return "daily_limit"

        if not wa.is_connected and not wa.wait_connected(RECONNECT_WAIT):
            emit("connection_lost", ())
            return "connection_lost"

        try:
            wa.send_text(number, message)
        except Exception as e:
            if not wa.is_connected:
                # Nothing was recorded: this number stays queued.
                emit("connection_lost", ())
                return "connection_lost"
            if "no LID found" in str(e):
                _record(number, STATUS_NOT_ON_WHATSAPP)
                emit("not_on_whatsapp", (number,))
            else:
                _record(number, STATUS_FAILED, error=str(e))
                emit("failed", (number, e))
        else:
            _record(number, STATUS_SENT)
            sent_today += 1
            emit("sent", (number,))

        counts_changed()

        if index < len(sendable) - 1:
            _sleep(random.uniform(settings["delay_min"], settings["delay_max"]), should_stop)

    emit("completed", ())
    return "completed"


def _record(number, status, error=None):
    """Write the outcome and take the number off the queue atomically."""
    with Session() as session:
        row = session.query(Pool).filter(Pool.number == number).first()
        if row is None:
            row = Pool(number=number)
            session.add(row)
        row.status = status
        row.error = error
        row.sent_at = utcnow() if status == STATUS_SENT else None
        session.query(TempNumbers).filter(TempNumbers.number == number).delete()
        session.commit()


def _remove_from_queue(numbers, chunk=500):
    if not numbers:
        return
    with Session() as session:
        for start in range(0, len(numbers), chunk):
            session.query(TempNumbers).filter(
                TempNumbers.number.in_(numbers[start:start + chunk])
            ).delete(synchronize_session=False)
        session.commit()


def _sent_today():
    """Count of messages sent since the user's local midnight (naive UTC in the DB)."""
    midnight = (datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
                .astimezone(timezone.utc).replace(tzinfo=None))
    with Session() as session:
        return session.query(Pool).filter(
            Pool.status == STATUS_SENT, Pool.sent_at >= midnight).count()


def _sleep(seconds, should_stop):
    """Sleep in small steps so Stop reacts quickly."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if should_stop():
            return
        time.sleep(min(0.2, max(0.0, end - time.monotonic())))
