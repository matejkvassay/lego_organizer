
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app import config, db
from app.db import include_object


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    path = tmp_path / "m.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    config.get_settings.cache_clear()
    db.reset_engine()
    yield path
    config.get_settings.cache_clear()
    db.reset_engine()


def test_fresh_database_gets_tables_fts_and_version(fresh_db):
    db.init_db()
    insp = inspect(db.get_engine())
    assert {"items", "tags", "item_tags", "brickset_sets", "item_fts", "alembic_version"} <= set(insp.get_table_names())
    with db.get_engine().connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"


def test_migrations_match_models(fresh_db):
    """If someone edits models.py without adding a migration, this fails."""
    db.init_db()
    with db.get_engine().connect() as c:
        diff = compare_metadata(MigrationContext.configure(c, opts={"include_object": include_object}), db.Base.metadata)
    assert diff == []


def test_init_db_twice_is_a_noop(fresh_db):
    db.init_db()
    db.init_db()


def test_v01_database_is_adopted_with_its_data(fresh_db):
    """A DB made by v0.1 (create_all, no alembic_version) keeps its rows when migrations arrive."""
    from app import models  # noqa: F401
    db.Base.metadata.create_all(db.get_engine())
    with db.get_engine().begin() as c:
        c.execute(text("CREATE VIRTUAL TABLE item_fts USING fts5(title, number, theme, subtheme, tags, box, notes)"))
        c.execute(text("INSERT INTO items (type, box, notes, title, added_at) VALUES ('other', 'A1', '', 'Old brick', '2026-01-01')"))
    db.reset_engine()

    db.init_db()

    with db.get_engine().connect() as c:
        assert c.execute(text("SELECT title FROM items")).scalar() == "Old brick"
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"
