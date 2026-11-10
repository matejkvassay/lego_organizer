import pytest
from conftest import fake_set
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from app import agent, brickset
from app.db import get_session


@pytest.fixture
def remote(monkeypatch):
    """Fake the Brickset API with a small catalog."""
    catalog = [
        fake_set(1, "75159", "Death Star", "Star Wars", "Episode IV"),
        fake_set(2, "7305", "Pharaoh's Quest Forbidden Ruins", "Pharaoh's Quest", "", 2011),
        fake_set(3, "75257", "Millennium Falcon", "Star Wars", "Episode IX", 2019),
    ]
    calls = []

    def search_remote(params):
        calls.append(params)
        if "query" in params:
            q = params["query"].lower()
            return [s for s in catalog if any(w in s["name"].lower() or w in s["theme"].lower() for w in q.split())]
        if "setNumber" in params:
            n = params["setNumber"].split("-")[0]
            return [s for s in catalog if s["number"] == n]
        return []

    monkeypatch.setattr(brickset, "search_remote", search_remote)
    return calls


def add_set(client, set_id, **kw):
    return client.post("/api/items", json={"type": "set", "brickset_set_id": set_id, **kw})


def test_keyword_search_then_add_and_browse(client, remote):
    r = client.post("/api/catalog/search", json={"query": "falcon", "mode": "keyword"})
    assert [c["name"] for c in r.json()] == ["Millennium Falcon"]
    sid = r.json()[0]["set_id"]

    r = add_set(client, sid, box="587B", tags=["modern", "Display"], notes="missing 2 pieces")
    assert r.status_code == 201
    assert r.json()["title"] == "Millennium Falcon"

    f = client.get("/api/facets").json()
    assert f["themes"] == [{"name": "Star Wars", "count": 1, "subthemes": [{"name": "Episode IX", "count": 1}]}]
    assert [b["name"] for b in f["boxes"]] == ["587B"]
    assert {t["name"] for t in f["tags"]} == {"modern", "Display"}
    assert len(client.get("/api/items", params={"theme": "Star Wars"}).json()) == 1
    assert client.get("/api/items", params={"tag": "modern"}).json()[0]["box"] == "587B"


def test_collection_search_bm25_covers_number_box_notes(client, remote):
    for sid in (1, 3):
        brickset.search(next(get_session()), "star")
    a = add_set(client, 1, box="A1", notes="battered").json()["id"]
    b = add_set(client, 3, box="B7").json()["id"]
    other = client.post("/api/items", json={"type": "other", "title": "Spare parts", "box": "S1",
                                            "description": "separators and loose plates"}).json()["id"]
    ids = lambda q: [i["id"] for i in client.get("/api/items", params={"q": q}).json()]
    assert ids("75159") == [a]
    assert ids("falc") == [b]
    assert ids("battered") == [a]
    assert ids("B7") == [b]
    assert ids("separators") == [other]
    assert set(ids("star wars")) == {a, b}
    assert ids("nonexistent") == []


def test_edit_and_delete_keep_index_and_tags_clean(client, remote):
    brickset.search(next(get_session()), "star")
    i = add_set(client, 1, box="A1", tags=["x"]).json()["id"]
    client.patch(f"/api/items/{i}", json={"box": "Z9", "tags": ["y"]})
    assert client.get("/api/items", params={"q": "Z9"}).json()[0]["id"] == i
    assert client.get("/api/items", params={"q": "A1"}).json() == []
    assert client.delete(f"/api/items/{i}").status_code == 204
    assert client.get("/api/items", params={"q": "Z9"}).json() == []
    assert client.get("/api/facets").json()["tags"] == []
    assert client.get(f"/api/items/{i}").status_code == 404


def test_add_unknown_set_and_empty_other_rejected(client):
    assert add_set(client, 999).status_code == 422
    assert client.post("/api/items", json={"type": "other", "title": " "}).status_code == 422


def test_export(client, remote):
    brickset.search(next(get_session()), "star")
    add_set(client, 1, box="A1", tags=["a", "b"])
    csv_text = client.get("/api/export.csv").text
    assert "75159" in csv_text and "a;b" in csv_text
    assert client.get("/api/export.json").json()[0]["box"] == "A1"


def test_get_by_number_is_cache_first(client, remote):
    db = next(get_session())
    assert brickset.get_by_number(db, "75159").name == "Death Star"
    assert brickset.get_by_number(db, "75159-1").name == "Death Star"
    assert len(remote) == 1  # second lookup hit the cache


def _scripted_model(final_ids):
    def fn(messages, info):
        if not any(isinstance(p, ToolReturnPart) for m in messages for p in m.parts):
            return ModelResponse(parts=[ToolCallPart("search_brickset", {"query": "pharaoh"})])
        cands = [{"set_id": i, "number": "?", "name": "?", "reason": "fits"} for i in final_ids]
        return ModelResponse(parts=[ToolCallPart("final_result", {"candidates": cands})])
    return FunctionModel(fn)


async def test_agent_returns_only_real_candidates(client, remote):
    db = next(get_session())
    out = await agent.find_candidates(db, "pharaoh castle adventurers", model=_scripted_model([2, 424242]))
    assert [c.set_id for c in out] == [2]  # hallucinated id dropped
    assert out[0].name == "Pharaoh's Quest Forbidden Ruins"
    assert out[0].reason == "fits"
    assert len(remote) == 1  # one tool call, within budget


def test_login_redirects_to_canonical_host(client, monkeypatch):
    from app import config
    monkeypatch.setenv("BASE_URL", "http://localhost:8000")
    config.get_settings.cache_clear()
    r = client.get("/auth/login", follow_redirects=False)  # TestClient host is "testserver"
    assert r.status_code == 307 and r.headers["location"] == "http://localhost:8000/auth/login"


def test_callback_without_session_redirects_with_error(client, monkeypatch):
    r = client.get("/auth/callback?state=x&code=y", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/?login_error=failed"


def test_me_returns_signed_in_email(client):
    assert client.get("/auth/me").json() == {"email": "test@local"}


def test_api_requires_login(client, monkeypatch):
    client.app.dependency_overrides.clear()  # drop the test stub: real session check applies
    monkeypatch.setenv("ALLOWED_EMAIL", "me@example.com")
    from app import config
    config.get_settings.cache_clear()
    assert client.get("/api/facets").status_code == 401
    assert client.get("/api/export.csv").status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_seed_is_offline_and_idempotent(client, capsys):
    from app import seed
    seed.main(); seed.main()
    items = client.get("/api/items").json()
    assert len(items) >= 3 and all(i["set"] for i in items)
    assert client.get("/api/items", params={"q": "death star"}).json()  # searchable straight after seeding
    assert "already present" in capsys.readouterr().out


def _static_app(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app import config
    from app.main import create_app
    dist = tmp_path / "site" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "site" / "secret.txt").write_text("TOP SECRET")  # sits next to dist, like .env / the DB would
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    config.get_settings.cache_clear()
    return TestClient(create_app())


def test_static_route_blocks_path_traversal(client, tmp_path, monkeypatch):
    c = _static_app(tmp_path, monkeypatch)
    assert c.get("/").text == "<html>spa</html>"
    assert c.get("/assets/app.js").status_code == 200
    for evil in ["/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt", "/assets/../../secret.txt",
                 "/%2e%2e%2fsecret.txt", "//etc/passwd", "/....//secret.txt"]:
        r = c.get(evil)
        assert "TOP SECRET" not in r.text and "root:" not in r.text, evil
    # unknown API paths are a 404, not the SPA shell
    assert c.get("/api/nope").status_code in (401, 404)
    assert c.get("/auth/nope").status_code == 404


def test_weak_session_secret_refuses_to_start(client, monkeypatch):
    from app import config
    from app.main import create_app
    for bad in ["", "change-me", "change-me-to-a-long-random-string", "short"]:
        monkeypatch.setenv("SESSION_SECRET", bad)
        config.get_settings.cache_clear()
        with pytest.raises(RuntimeError):
            create_app()


def test_security_headers_and_no_public_docs(client):
    r = client.get("/auth/me")
    assert r.headers["X-Frame-Options"] == "DENY" and r.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert client.get("/docs").status_code == 404 and client.get("/openapi.json").status_code == 404


def test_errors_do_not_leak_internals(client, monkeypatch):
    def boom(*a, **k): raise RuntimeError("secret internal detail proj_ABC123")
    monkeypatch.setattr(brickset, "search_remote", boom)
    r = client.post("/api/catalog/search", json={"query": "x", "mode": "keyword"})
    assert r.status_code == 502 and "proj_ABC123" not in r.text


# ---------- Phase 0/1: health, logout, logging ----------

def test_healthz_is_public_and_touches_db(client):
    client.app.dependency_overrides.clear()  # no login: Cloud Run probes are anonymous
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_healthz_fails_when_db_is_down(client, monkeypatch):
    from app import main
    def boom(*a, **k): raise RuntimeError("db gone")
    monkeypatch.setattr(main, "check_db", boom)
    assert client.get("/healthz").status_code == 503


def test_logout_requires_post_and_clears_session(client):
    assert client.get("/auth/logout").status_code in (404, 405)  # a cross-site <img>/link must not log you out
    r = client.post("/auth/logout")
    assert r.status_code == 204


def test_json_logs_never_contain_query_string_or_secrets(client, capsys):
    import json
    client.get("/auth/callback?state=SECRETSTATE&code=SECRETCODE", follow_redirects=False)
    # Server-side lines only: the TestClient's own HTTP-client logger echoes the URL it requested.
    lines = [json.loads(ln) for ln in capsys.readouterr().err.splitlines() if ln.startswith("{")]
    server = [ln for ln in lines if not ln["logger"].startswith("httpx")]
    assert server and "SECRETCODE" not in json.dumps(server) and "SECRETSTATE" not in json.dumps(server)
    line = next(ln for ln in server if "path" in ln)
    assert line["path"] == "/auth/callback" and line["status"] == 307 and line["method"] == "GET"
    assert "cookie" not in json.dumps(line).lower()
