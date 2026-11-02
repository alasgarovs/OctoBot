"""Excel import/export. No Qt imports here.

Progress and messages are reported through plain callbacks, so any UI can use this.
"""

import os
from datetime import timezone

import pandas as pd

from core.db import Pool, Session, TempNumbers
from core.phone import clean_number

REPORT_EVERY = 500


def _local_time(stamp):
    """A naive-UTC timestamp from the DB as naive local time for the report."""
    if stamp is None:
        return None
    return stamp.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


def import_numbers(file_path, emit, progress=None, should_stop=None):
    """Load the first column of an Excel file into the TempNumbers queue.

    emit(key, args) keys: read_error, empty, no_valid, uploading, success,
    skipped, db_error. Returns True when new numbers were queued.
    """
    should_stop = should_stop or (lambda: False)
    file_name = os.path.basename(file_path)
    engine = "openpyxl" if os.path.splitext(file_path)[1].lower() == ".xlsx" else "xlrd"

    try:
        frame = pd.read_excel(file_path, sheet_name=0, header=None, engine=engine)
    except Exception as e:
        emit("read_error", (file_name, e))
        return False

    if frame.empty or frame.shape[1] == 0:
        emit("empty", (file_name,))
        return False

    column = frame.iloc[:, 0]
    total = len(column)
    valid, invalid_count = [], 0

    for index, value in enumerate(column, 1):
        if should_stop():
            return False

        number = clean_number(value)
        if number is None:
            invalid_count += 1
        else:
            valid.append(number)

        if progress and (index % REPORT_EVERY == 0 or index == total):
            progress(index, total)

    if not valid:
        emit("no_valid", (file_name, invalid_count))
        return False

    unique = list(dict.fromkeys(valid))
    duplicate_count = len(valid) - len(unique)

    emit("uploading", (file_name,))

    try:
        # One transaction: a failure rolls back to the old queue.
        with Session() as session:
            session.query(TempNumbers).delete()
            session.add_all(TempNumbers(number=number) for number in unique)
            session.commit()
    except Exception as e:
        emit("db_error", (e,))
        return False

    emit("success", (file_name, len(unique)))
    if invalid_count or duplicate_count:
        emit("skipped", (invalid_count, duplicate_count))
    return True


def export_pool(file_path):
    """Write the Pool to an .xlsx file. Raises on failure."""
    with Session() as session:
        rows = session.query(
            Pool.number, Pool.status, Pool.error, Pool.sent_at
        ).order_by(Pool.id).all()

    data = [
        {
            "Number": row.number,
            "Status": row.status,
            "Error": row.error or "",
            "Sent at": _local_time(row.sent_at),
        }
        for row in rows
    ]
    pd.DataFrame(data, columns=["Number", "Status", "Error", "Sent at"]).to_excel(
        file_path, index=False
    )
