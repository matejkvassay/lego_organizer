import pytest
from fastapi.testclient import TestClient

from app import config, db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("BRICKSET_API_KEY", "test")
    monkeypatch.setenv("SESSION_SECRET", "t" * 40)
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "nodist"))
    config.get_settings.cache_clear()
    db.reset_engine()
    from app.auth import current_user
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[current_user] = lambda: "test@local"  # tests act as the signed-in owner
    with TestClient(app) as c:
        yield c
    config.get_settings.cache_clear()
    db.reset_engine()


def fake_set(set_id=1, number="75159", name="Death Star", theme="Star Wars", subtheme="Episode IV", year=2016):
    return {
        "setID": set_id, "number": number, "numberVariant": 1, "name": name, "year": year,
        "theme": theme, "subtheme": subtheme, "pieces": 4016, "minifigs": 23,
        "image": {"imageURL": "http://x/i.jpg", "thumbnailURL": "http://x/t.jpg"},
        "bricksetURL": "http://x",
    }
