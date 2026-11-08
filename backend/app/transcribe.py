import httpx

from .config import get_settings


async def transcribe(audio: bytes, filename: str, content_type: str) -> str:
    s = get_settings()
    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {s.openai_api_key}"},
            data={"model": s.transcribe_model},
            files={"file": (filename, audio, content_type)},
        )
    r.raise_for_status()
    return r.json()["text"].strip()
