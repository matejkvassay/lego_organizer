"""Collection search: SQLite FTS5 with BM25 ranking. No AI."""
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Item


def item_title(item: Item) -> str:
    if item.type == "set" and item.brickset_set:
        return item.brickset_set.name
    return item.title or ""


def reindex_item(db: Session, item: Item) -> None:
    db.execute(text("DELETE FROM item_fts WHERE rowid = :id"), {"id": item.id})
    bs = item.brickset_set
    db.execute(
        text(
            "INSERT INTO item_fts(rowid, title, number, theme, subtheme, tags, box, notes) "
            "VALUES (:id, :title, :number, :theme, :subtheme, :tags, :box, :notes)"
        ),
        {
            "id": item.id,
            "title": item_title(item) + (" " + (item.description or "") if item.type == "other" else ""),
            "number": bs.number if bs else "",
            "theme": (bs.theme or "") if bs else "",
            "subtheme": (bs.subtheme or "") if bs else "",
            "tags": " ".join(t.name for t in item.tags),
            "box": item.box,
            "notes": item.notes,
        },
    )


def remove_item(db: Session, item_id: int) -> None:
    db.execute(text("DELETE FROM item_fts WHERE rowid = :id"), {"id": item_id})


def _fts_query(q: str) -> str:
    # Every token becomes a quoted prefix term, AND-ed together.
    tokens = re.findall(r"[\w]+", q, flags=re.UNICODE)
    return " ".join(f'"{t}"*' for t in tokens)


def search_ids(db: Session, q: str) -> list[int]:
    fq = _fts_query(q)
    if not fq:
        return []
    rows = db.execute(
        text("SELECT rowid FROM item_fts WHERE item_fts MATCH :q ORDER BY bm25(item_fts, 10, 8, 2, 2, 4, 6, 1)"),
        {"q": fq},
    ).all()
    return [r[0] for r in rows]


def reindex_all(db: Session) -> None:
    db.execute(text("DELETE FROM item_fts"))
    for item in db.query(Item).all():
        reindex_item(db, item)
    db.commit()
