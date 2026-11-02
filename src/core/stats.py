"""Read-only queries for the dashboard and the contacts table. No Qt imports here."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func

from core.db import (Pool, STATUS_FAILED, STATUS_NOT_ON_WHATSAPP, STATUS_SENT,
                     Session, TempNumbers)

CHART_DAYS = 7


def _local_midnight_utc():
    """Local midnight expressed as naive UTC (the DB stores naive UTC)."""
    return (datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(timezone.utc).replace(tzinfo=None))


def _tz_modifier():
    """The local UTC offset as a SQLite date modifier, e.g. '+4 hours'."""
    offset = datetime.now().astimezone().utcoffset() or timedelta(0)
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    return f"{sign}{abs(total) / 3600:g} hours"


def get_stats():
    """Counters, today's sent count and a per-day history of the last 7 days.

    "Today" and the chart days follow the user's local clock. The history is
    aggregated by SQLite (GROUP BY day), so it stays cheap with many rows.
    """
    now_local = datetime.now().astimezone()
    midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    first_day_local = midnight_local - timedelta(days=CHART_DAYS - 1)
    midnight = midnight_local.astimezone(timezone.utc).replace(tzinfo=None)
    first_day = first_day_local.astimezone(timezone.utc).replace(tzinfo=None)
    modifier = _tz_modifier()

    with Session() as session:
        queue = session.query(TempNumbers).count()
        totals = dict(session.query(Pool.status, func.count()).group_by(Pool.status).all())

        sent_today = session.query(Pool).filter(
            Pool.status == STATUS_SENT, Pool.sent_at >= midnight).count()

        history = {STATUS_SENT: {}, STATUS_NOT_ON_WHATSAPP: {}, STATUS_FAILED: {}}
        sent_day = func.date(Pool.sent_at, modifier)
        for day, count in (session.query(sent_day, func.count())
                           .filter(Pool.status == STATUS_SENT, Pool.sent_at >= first_day)
                           .group_by(sent_day).all()):
            history[STATUS_SENT][date.fromisoformat(day)] = count

        other_day = func.date(Pool.updated_date, modifier)
        for status, day, count in (session.query(Pool.status, other_day, func.count())
                                   .filter(Pool.status != STATUS_SENT,
                                           Pool.updated_date >= first_day)
                                   .group_by(Pool.status, other_day).all()):
            if status in history:
                history[status][date.fromisoformat(day)] = count

    days = []
    for offset in range(CHART_DAYS):
        day = first_day_local.date() + timedelta(days=offset)
        days.append({
            "date": day,
            "sent": history[STATUS_SENT].get(day, 0),
            "not_on_whatsapp": history[STATUS_NOT_ON_WHATSAPP].get(day, 0),
            "failed": history[STATUS_FAILED].get(day, 0),
        })

    return {
        "queue": queue,
        "sent": totals.get(STATUS_SENT, 0),
        "not_on_whatsapp": totals.get(STATUS_NOT_ON_WHATSAPP, 0),
        "failed": totals.get(STATUS_FAILED, 0),
        "pool": sum(totals.values()),
        "sent_today": sent_today,
        "days": days,
    }


def list_pool(status=None, search="", offset=0, limit=14):
    """One page of the Pool: (rows, total matching rows)."""
    with Session() as session:
        query = session.query(Pool)
        if status:
            query = query.filter(Pool.status == status)
        search = (search or "").strip().lstrip("+")
        if search:
            query = query.filter(Pool.number.contains(search))
        total = query.count()
        rows = query.order_by(Pool.id.desc()).offset(offset).limit(limit).all()
        result = [
            {"number": row.number, "status": row.status, "error": row.error or "",
             "sent_at": row.sent_at}
            for row in rows
        ]
    return result, total
