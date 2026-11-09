"""Load a few example sets so a fresh install isn't empty: `python -m app.seed`.

Works offline (no Brickset key needed): the data comes from seed_data.json.
Safe to run twice; sets that are already in the collection are skipped.
"""
import json
from pathlib import Path

from . import service
from .db import get_session, init_db
from .models import BricksetSet, Item
from .schemas import ItemCreate

DATA = Path(__file__).with_name("seed_data.json")


def main() -> None:
    init_db()
    db = next(get_session())
    for entry in json.loads(DATA.read_text()):
        s = entry["set"]
        if db.query(Item).filter(Item.brickset_set_id == s["set_id"]).first():
            print(f"= {s['number']} {s['name']} already present")
            continue
        db.merge(BricksetSet(**s))
        db.commit()
        service.create_item(db, ItemCreate(type="set", brickset_set_id=s["set_id"], box=entry["box"],
                                           tags=entry["tags"], notes=entry["notes"]))
        print(f"+ {s['number']}-{s['number_variant']} {s['name']} -> {entry['box']}")


if __name__ == "__main__":
    main()
