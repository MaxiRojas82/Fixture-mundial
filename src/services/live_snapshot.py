"""Lee el snapshot de partidos en vivo que el notificador (GitHub Actions)
escribe en Firestore a partir de API-Football.

El plan gratuito de API-Football permite 100 consultas/día, así que la app
nunca la consulta directo: el notificador hace una consulta por corrida y
publica el resultado acá para todos los dispositivos.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

_API_KEY = os.getenv("FIREBASE_API_KEY", "")
_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_URL = (f"https://firestore.googleapis.com/v1/projects/{_PROJECT_ID}"
        f"/databases/(default)/documents/notifier_state/live_snapshot")


def is_configured() -> bool:
    return bool(_API_KEY and _PROJECT_ID)


def _parse(raw: dict):
    if "stringValue" in raw:
        return raw["stringValue"]
    if "integerValue" in raw:
        return int(raw["integerValue"])
    if "nullValue" in raw:
        return None
    if "mapValue" in raw:
        return {k: _parse(v) for k, v in raw["mapValue"].get("fields", {}).items()}
    return None


async def fetch() -> dict[int, dict]:
    """Retorna {fd_match_id: {"status": short, "minute": int|None,
    "home": int|None, "away": int|None}} — vacío si no hay snapshot."""
    if not is_configured():
        return {}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(_URL, params={"key": _API_KEY})
    if r.status_code != 200:
        return {}
    fields = {k: _parse(v) for k, v in r.json().get("fields", {}).items()}
    matches = fields.get("matches") or {}
    out: dict[int, dict] = {}
    for mid, data in matches.items():
        try:
            out[int(mid)] = data
        except (ValueError, TypeError):
            continue
    return out
