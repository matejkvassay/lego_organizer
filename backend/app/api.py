import csv
import io
import logging
from collections import Counter, defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import agent, brickset, search, service, transcribe
from .auth import current_user
from .db import get_session
from .models import BricksetSet, Item, Tag
from .schemas import Candidate, ItemCreate, ItemOut, ItemUpdate

log = logging.getLogger(__name__)
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # OpenAI's own limit

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


# ---------- collection ----------

@router.get("/items", response_model=list[ItemOut])
def list_items(
    q: str = "",
    type: Literal["set", "other", ""] = "",
    theme: str = "",
    subtheme: str = "",
    tag: str = "",
    box: str = "",
    db: Session = Depends(get_session),
):
    query = db.query(Item)
    if q.strip():
        ids = search.search_ids(db, q)
        if not ids:
            return []
        query = query.filter(Item.id.in_(ids))
    if type:
        query = query.filter(Item.type == type)
    if box:
        query = query.filter(Item.box == box)
    if tag:
        query = query.filter(Item.tags.any(Tag.name == tag))
    if theme:
        query = query.filter(Item.brickset_set.has(BricksetSet.theme == theme))
    if subtheme:
        query = query.filter(Item.brickset_set.has(BricksetSet.subtheme == subtheme))
    items = query.all()
    if q.strip():  # keep BM25 order
        rank = {i: n for n, i in enumerate(ids)}
        items.sort(key=lambda i: rank[i.id])
    else:
        items.sort(key=lambda i: search.item_title(i).lower())
    return [service.to_out(i) for i in items]


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_session)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404)
    return service.to_out(item)


@router.post("/items", response_model=ItemOut, status_code=201)
def create_item(data: ItemCreate, db: Session = Depends(get_session)):
    try:
        return service.to_out(service.create_item(db, data))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, data: ItemUpdate, db: Session = Depends(get_session)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404)
    return service.to_out(service.update_item(db, item, data))


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_session)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404)
    service.delete_item(db, item)


@router.get("/facets")
def facets(db: Session = Depends(get_session)):
    """Everything the drill-down navigation needs, in one call."""
    items = db.query(Item).all()
    themes: dict[str, Counter] = defaultdict(Counter)
    tags, boxes, others = Counter(), Counter(), 0
    for i in items:
        if i.type == "set" and i.brickset_set:
            themes[i.brickset_set.theme or "Unknown"][i.brickset_set.subtheme or ""] += 1
        else:
            others += 1
        for t in i.tags:
            tags[t.name] += 1
        if i.box:
            boxes[i.box] += 1
    return {
        "total": len(items),
        "others": others,
        "themes": [
            {"name": t, "count": sum(c.values()),
             "subthemes": [{"name": s, "count": n} for s, n in sorted(c.items()) if s]}
            for t, c in sorted(themes.items())
        ],
        "tags": [{"name": n, "count": c} for n, c in sorted(tags.items())],
        "boxes": [{"name": n, "count": c} for n, c in sorted(boxes.items())],
    }


# ---------- add flow ----------

class CatalogSearch(BaseModel):
    query: str
    mode: Literal["ai", "keyword"] = "ai"


@router.post("/catalog/search", response_model=list[Candidate])
async def catalog_search(body: CatalogSearch, db: Session = Depends(get_session)):
    q = body.query.strip()
    if not q:
        return []
    try:
        if body.mode == "ai":
            return await agent.find_candidates(db, q)
        sets = brickset.search(db, q, page_size=20)
    except brickset.BricksetError as e:
        raise HTTPException(502, str(e))
    except Exception:  # LLM / network failures shouldn't look like a server crash
        log.exception("catalog search failed")  # details stay in the server log, not in the response
        raise HTTPException(502, "Search failed. Please try again.")
    return [agent._candidate(s) for s in sets]


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    audio = await file.read(MAX_AUDIO_BYTES + 1)
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording too large")
    try:
        text = await transcribe.transcribe(audio, "speech.webm", file.content_type or "audio/webm")
    except Exception:
        log.exception("transcription failed")
        raise HTTPException(502, "Transcription failed. Please try again.")
    return {"text": text}


# ---------- export ----------

@router.get("/export.json")
def export_json(db: Session = Depends(get_session)):
    items = [service.to_out(i).model_dump() for i in db.query(Item).order_by(Item.id)]
    import json
    return Response(json.dumps(items, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="lego-collection.json"'})


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_session)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["type", "number", "name", "theme", "subtheme", "year", "pieces", "box", "tags", "notes"])
    for i in db.query(Item).order_by(Item.id):
        o = service.to_out(i)
        s = o.set
        w.writerow([o.type, s.number if s else "", o.title, s.theme if s else "", s.subtheme if s else "",
                    s.year if s else "", s.pieces if s else "", o.box, ";".join(o.tags), o.notes])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="lego-collection.csv"'})
