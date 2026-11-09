from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        url = get_settings().database_url
        if url.startswith("sqlite:///") and ":memory:" not in url:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _pragmas(dbapi_conn, _):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()
        _SessionLocal = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def get_session() -> Iterator[Session]:
    get_engine()
    with _SessionLocal() as s:
        yield s


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Alembic filter: the FTS5 virtual table and its shadow tables are managed by hand, not by the models."""
    return not (type_ == "table" and name.startswith("item_fts"))


def init_db() -> None:
    """Bring the database to the latest schema (creates it on first run)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).with_name("migrations")))
    get_engine()  # also creates the parent folder of a SQLite file
    command.upgrade(cfg, "head")


def check_db() -> None:
    """Raise if the database cannot be queried (used by /healthz)."""
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
