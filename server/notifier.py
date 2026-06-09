#!/usr/bin/env python3
"""
MaxFixture FCM Notifier — corre cada 5 minutos via GitHub Actions.

Detecta goles y eventos en partidos en vivo del Mundial y envía
push notifications a todos los dispositivos suscritos al topic FCM.

Estado entre ejecuciones se persiste en Firestore (notifier_state/matches).
"""

import asyncio
import json
import os
import sys
import httpx
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from dotenv import load_dotenv

load_dotenv()

FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
COMPETITION_ID   = os.environ.get("WORLD_CUP_COMPETITION_ID", "2000")
FCM_TOPIC        = "maxfixture_events"
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_MULTIPLIER = 2

LIVE_STATUSES = {"IN_PLAY", "PAUSED", "EXTRA_TIME", "PENALTY_SHOOTOUT"}


# ── Firebase ──────────────────────────────────────────────────────────────────

def init_firebase() -> firestore.Client:
    if not firebase_admin._apps:
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if not cred_json:
            print("ERROR: FIREBASE_CREDENTIALS_JSON no configurado.", file=sys.stderr)
            sys.exit(1)
        cred = credentials.Certificate(json.loads(cred_json))
        firebase_admin.initialize_app(cred)
    return firestore.client()


# ── API football-data.org ─────────────────────────────────────────────────────

async def get_live_matches() -> list[dict]:
    url = "https://api.football-data.org/v4/matches"
    async with httpx.AsyncClient(timeout=20) as client:
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                resp = await client.get(
                    url,
                    headers={"X-Auth-Token": FOOTBALL_API_KEY},
                    params={"competitions": COMPETITION_ID, "status": "LIVE"},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("matches", [])
            except httpx.RequestError as e:
                if attempt == MAX_RETRY_ATTEMPTS:
                    raise
                wait_seconds = RETRY_BACKOFF_MULTIPLIER ** (attempt - 1)
                print(
                    f"⚠️ Error de red al consultar la API ({type(e).__name__}: {e}). "
                    f"Reintentando en {wait_seconds}s..."
                )
                await asyncio.sleep(wait_seconds)


# ── Estado en Firestore ───────────────────────────────────────────────────────

def load_state(db: firestore.Client) -> dict:
    doc = db.collection("notifier_state").document("matches").get()
    return doc.to_dict() if doc.exists else {}


def save_state(db: firestore.Client, state: dict) -> None:
    db.collection("notifier_state").document("matches").set(state)


# ── Snapshot y detección de eventos ──────────────────────────────────────────

def snapshot(match: dict) -> dict:
    score = match.get("score", {})
    full  = score.get("fullTime", {})
    ht    = score.get("halfTime", {})
    return {
        "status":    match.get("status", ""),
        "home":      full.get("home"),
        "away":      full.get("away"),
        "ht_home":   ht.get("home"),
        "ht_away":   ht.get("away"),
        "home_name": match.get("homeTeam", {}).get("shortName")
                     or match.get("homeTeam", {}).get("name", "Local"),
        "away_name": match.get("awayTeam", {}).get("shortName")
                     or match.get("awayTeam", {}).get("name", "Visitante"),
    }


def detect_events(mid: str, prev_state: dict, curr: dict) -> list[tuple[str, str]]:
    """Retorna lista de (titulo, cuerpo) para cada evento nuevo detectado."""
    prev   = prev_state.get(mid, {})
    events: list[tuple[str, str]] = []

    home = curr["home_name"]
    away = curr["away_name"]
    ch   = curr["home"] or 0
    ca   = curr["away"] or 0

    # ── Cambios de estado ────────────────────────────────────
    ps = prev.get("status", "")
    cs = curr["status"]

    if ps in ("SCHEDULED", "TIMED", "") and cs in LIVE_STATUSES:
        events.append(("▶️ Inicio del partido", f"{home} vs {away}"))

    elif ps == "IN_PLAY" and cs == "PAUSED":
        ph = prev.get("home") or 0
        pa = prev.get("away") or 0
        events.append(("⏸ Medio tiempo", f"{home} {ph} – {pa} {away}"))

    elif ps in LIVE_STATUSES | {"PAUSED"} and cs == "FINISHED":
        events.append(("🏁 Partido finalizado", f"{home} {ch} – {ca} {away}"))

    # ── Goles ────────────────────────────────────────────────
    if prev:
        ph = prev.get("home") or 0
        pa = prev.get("away") or 0
        for _ in range(max(0, ch - ph)):
            events.append((f"⚽ ¡GOL de {home}!", f"{home} {ch} – {ca} {away}"))
        for _ in range(max(0, ca - pa)):
            events.append((f"⚽ ¡GOL de {away}!", f"{home} {ch} – {ca} {away}"))

    return events


# ── FCM ───────────────────────────────────────────────────────────────────────

def send_notification(title: str, body: str, match_id: str) -> None:
    msg = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={"matchId": match_id},
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="maxfixture_goals",
                sound="default",
                priority="high",
                tag=match_id,
            ),
        ),
        topic=FCM_TOPIC,
    )
    result = messaging.send(msg)
    print(f"  ✓ FCM enviado → {title} | msg_id={result}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    if not FOOTBALL_API_KEY:
        print("ERROR: FOOTBALL_API_KEY no configurado.", file=sys.stderr)
        sys.exit(1)

    db = init_firebase()

    print("🔍 Consultando partidos en vivo...")
    try:
        live = await get_live_matches()
    except httpx.RequestError as e:
        print(
            f"ERROR de red al consultar API: {e}. "
            "Esta ejecución finaliza; se reintentará en el próximo ciclo programado.",
            file=sys.stderr,
        )
        return
    except httpx.HTTPStatusError as e:
        print(f"ERROR API: {e.response.status_code}", file=sys.stderr)
        sys.exit(1)

    print(f"   {len(live)} partido(s) en vivo")
    if not live:
        print("Sin partidos activos — fin.")
        return

    prev_state = load_state(db)
    new_state  = dict(prev_state)

    total_events = 0
    for match in live:
        mid  = str(match["id"])
        curr = snapshot(match)

        detected = detect_events(mid, prev_state, curr)
        for title, body in detected:
            print(f"  📣 {title}")
            send_notification(title, body, mid)
            total_events += 1

        new_state[mid] = {k: v for k, v in curr.items() if k not in ("home_name", "away_name")}

    save_state(db, new_state)
    print(f"\n✅ {total_events} evento(s) enviado(s). Estado guardado.")


if __name__ == "__main__":
    asyncio.run(main())
