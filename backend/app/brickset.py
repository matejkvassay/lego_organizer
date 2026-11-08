"""Brickset API v3 client + local cache.

Only `getSets` counts against the daily API limit, so every set we see is
cached in `brickset_sets` and looked up locally first.
"""
import json
from typing import Any

import httpx
from sqlalchemy.orm import Session

from .config import get_settings
from .models import BricksetSet


class BricksetError(Exception):
    pass


def _to_model(d: dict[str, Any]) -> BricksetSet:
    image = d.get("image") or {}
    return BricksetSet(
        set_id=d["setID"],
        number=str(d["number"]),
        number_variant=d.get("numberVariant") or 1,
        name=d["name"],
        year=d.get("year"),
        theme=d.get("theme"),
        subtheme=d.get("subtheme"),
        pieces=d.get("pieces"),
        minifigs=d.get("minifigs"),
        image_url=image.get("imageURL"),
        thumbnail_url=image.get("thumbnailURL"),
        brickset_url=d.get("bricksetURL"),
        raw=d,
    )


def search_remote(params: dict[str, Any]) -> list[dict[str, Any]]:
    s = get_settings()
    if not s.brickset_api_key:
        raise BricksetError("BRICKSET_API_KEY is not set")
    r = httpx.post(
        f"{s.brickset_base_url}/getSets",
        data={"apiKey": s.brickset_api_key, "userHash": "", "params": json.dumps(params)},
        timeout=20,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "success":
        raise BricksetError(body.get("message", "Brickset error"))
    return body.get("sets", [])


def search(db: Session, query: str = "", page_size: int = 10, *, theme: str = "", subtheme: str = "",
           year: str = "") -> list[BricksetSet]:
    """Search Brickset by keyword and/or filters; results are cached locally."""
    params: dict[str, Any] = {"pageSize": page_size, "orderBy": "YearFromDESC"}
    for key, val in (("query", query), ("theme", theme), ("subtheme", subtheme), ("year", year)):
        if val.strip():
            params[key] = val.strip()
    if len(params) == 2:
        return []
    raw = search_remote(params)
    out = []
    for d in raw:
        existing = db.get(BricksetSet, d["setID"])
        if existing is None:
            existing = db.merge(_to_model(d))
        out.append(existing)
    db.commit()
    return out


def get_by_number(db: Session, number: str) -> BricksetSet | None:
    """Cache-first lookup by set number ("75159" or "75159-1")."""
    num, _, variant = number.partition("-")
    q = db.query(BricksetSet).filter(BricksetSet.number == num)
    q = q.filter(BricksetSet.number_variant == int(variant or 1))
    hit = q.first()
    if hit:
        return hit
    found = search_remote({"setNumber": f"{num}-{variant or 1}"})
    if not found:
        return None
    m = db.merge(_to_model(found[0]))
    db.commit()
    return m
