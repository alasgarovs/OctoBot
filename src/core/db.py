"""Database models. No Qt imports here.

All timestamps are stored as naive UTC.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from core.paths import DB_PATH

STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_NOT_ON_WHATSAPP = "not_on_whatsapp"

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Pool(Base):
    """Every number that has been processed, with the outcome."""
    __tablename__ = "Pool"
    __table_args__ = (
        Index("ix_pool_status", "status"),
        Index("ix_pool_sent_at", "sent_at"),
    )

    id = Column(Integer, primary_key=True)
    number = Column(String(50), unique=True, nullable=False)
    status = Column(String(20), nullable=False, default=STATUS_FAILED)
    error = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_date = Column(DateTime, default=utcnow)
    updated_date = Column(DateTime, default=utcnow, onupdate=utcnow)


class TempNumbers(Base):
    """The queue: numbers imported from Excel that are still to be processed."""
    __tablename__ = "TempNumbers"
    __table_args__ = (Index("ix_temp_number", "number"),)

    id = Column(Integer, primary_key=True)
    number = Column(String(50), nullable=False)


class Message(Base):
    """A message template. Exactly one row is active at a time."""
    __tablename__ = "Message"

    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False, default="")
    message = Column(String(10000), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)


class Settings(Base):
    """Single row (id=1)."""
    __tablename__ = "Settings"

    id = Column(Integer, primary_key=True)
    delay_min = Column(Integer, nullable=False, default=3)    # seconds
    delay_max = Column(Integer, nullable=False, default=8)    # seconds
    daily_limit = Column(Integer, nullable=False, default=0)  # 0 = unlimited


def _migrate_message_templates():
    """Upgrade databases created before message templates existed.

    create_all() only builds new tables, so installs with an old Message
    table get the title/is_active columns here, the old rows named and
    the first one activated. Safe to run on every start.
    """
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(Message)"))}
        if "title" not in columns:
            conn.execute(text("ALTER TABLE Message ADD COLUMN title VARCHAR(100) NOT NULL DEFAULT ''"))
        if "is_active" not in columns:
            conn.execute(text("ALTER TABLE Message ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 0"))
        rows = conn.execute(text("SELECT id, title, is_active FROM Message ORDER BY id")).fetchall()
        for position, (row_id, title, _is_active) in enumerate(rows, 1):
            if not title:
                conn.execute(text("UPDATE Message SET title = :title WHERE id = :id"),
                             {"title": f"Message {position}", "id": row_id})
        if rows and not any(row[2] for row in rows):
            conn.execute(text("UPDATE Message SET is_active = 1 WHERE id = :id"),
                         {"id": rows[0][0]})


def _migrate_indexes():
    """Index the big-table queries; create_all only covers new databases."""
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pool_status ON Pool (status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pool_sent_at ON Pool (sent_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_temp_number ON TempNumbers (number)"))


engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"timeout": 30})
Base.metadata.create_all(engine)
_migrate_message_templates()
_migrate_indexes()
Session = sessionmaker(bind=engine)


def get_settings():
    """Return the settings as a plain dict, creating the default row if needed."""
    with Session() as session:
        row = session.get(Settings, 1)
        if row is None:
            row = Settings(id=1)
            session.add(row)
            session.commit()
        return {
            "delay_min": row.delay_min,
            "delay_max": row.delay_max,
            "daily_limit": row.daily_limit,
        }


def save_settings(delay_min, delay_max, daily_limit):
    delay_min = max(0, int(delay_min))
    delay_max = max(delay_min, int(delay_max))
    daily_limit = max(0, int(daily_limit))
    with Session() as session:
        row = session.get(Settings, 1)
        if row is None:
            row = Settings(id=1)
            session.add(row)
        row.delay_min, row.delay_max, row.daily_limit = delay_min, delay_max, daily_limit
        session.commit()
