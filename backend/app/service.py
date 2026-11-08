from sqlalchemy.orm import Session

from . import search
from .models import BricksetSet, Item, Tag
from .schemas import ItemCreate, ItemOut, ItemUpdate, SetOut


def to_out(item: Item) -> ItemOut:
    return ItemOut(
        id=item.id,
        type=item.type,
        title=search.item_title(item),
        description=item.description,
        box=item.box,
        notes=item.notes,
        tags=sorted(t.name for t in item.tags),
        set=SetOut.model_validate(item.brickset_set) if item.brickset_set else None,
    )


def _tags(db: Session, names: list[str]) -> list[Tag]:
    out, seen = [], set()
    for n in names:
        n = n.strip()
        if not n or n.lower() in seen:
            continue
        seen.add(n.lower())
        tag = db.query(Tag).filter(Tag.name.ilike(n)).first() or Tag(name=n)
        out.append(tag)
    return out


def create_item(db: Session, data: ItemCreate) -> Item:
    if data.type == "set":
        if data.brickset_set_id is None or db.get(BricksetSet, data.brickset_set_id) is None:
            raise ValueError("Unknown Brickset set; search for it first")
        item = Item(type="set", brickset_set_id=data.brickset_set_id)
    else:
        if not (data.title or "").strip():
            raise ValueError("Other items need a title")
        item = Item(type="other", title=data.title.strip(), description=data.description)
    item.box = data.box.strip()
    item.notes = data.notes
    item.tags = _tags(db, data.tags)
    db.add(item)
    db.flush()
    search.reindex_item(db, item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item: Item, data: ItemUpdate) -> Item:
    if data.box is not None:
        item.box = data.box.strip()
    if data.notes is not None:
        item.notes = data.notes
    if item.type == "other":
        if data.title is not None and data.title.strip():
            item.title = data.title.strip()
        if data.description is not None:
            item.description = data.description
    if data.tags is not None:
        item.tags = _tags(db, data.tags)
    db.flush()
    search.reindex_item(db, item)
    db.commit()
    return item


def delete_item(db: Session, item: Item) -> None:
    search.remove_item(db, item.id)
    db.delete(item)
    # drop tags no longer used
    db.flush()
    for tag in db.query(Tag).all():
        used = db.query(Item).filter(Item.tags.any(Tag.id == tag.id)).first()
        if not used:
            db.delete(tag)
    db.commit()
