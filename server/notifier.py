#!/usr/bin/env python3
"""
MaxFixture FCM Notifier — corre cada 5 minutos via GitHub Actions.

Fuente de datos en vivo: API-Football (plan gratuito, 100 req/día).
Para cuidar la cuota:
  - Solo consulta API-Football dentro de la ventana de un partido
    (10 min antes del inicio hasta ~3h45 después), según el fixture
    de football-data.org (gratuito e ilimitado para esto).
  - Una sola consulta por corrida cubre todos los partidos en vivo.
  - Contador diario en Firestore corta a las 92 consultas.

Además de enviar push notifications, publica un snapshot del estado en
vivo en Firestore (notifier_state/live_snapshot) que la app lee para
mostrar marcador y minuto sin gastar cuota de API-Football.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone, timedelta

import httpx
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from dotenv import load_dotenv

load_dotenv()

FOOTBALL_API_KEY  = os.environ.get("FOOTBALL_API_KEY", "")
API_FOOTBALL_KEY  = os.environ.get("API_FOOTBALL_KEY", "")
COMPETITION_ID    = os.environ.get("WORLD_CUP_COMPETITION_ID", "2000")
FCM_TOPIC         = "maxfixture_events"

AF_BASE   = "https://v3.football.api-sports.io"
AF_LEAGUE = 1      # FIFA World Cup en API-Football
AF_SEASON = 2026
AF_DAILY_BUDGET = 92

# Status de API-Football normalizados a los códigos del modelo de la app
_AF_STATUS_NORM = {
    "NS": "NS", "TBD": "NS",
    "1H": "1H", "HT": "HT", "2H": "2H",
    "ET": "ET", "BT": "ET", "P": "P",
    "SUSP": "2H", "INT": "2H",
    "FT": "FT", "AET": "FT", "PEN": "FT",
    "PST": "PST", "CANC": "CANC", "ABD": "CANC", "AWD": "FT", "WO": "FT",
}
_LIVE_SHORTS = {"1H", "HT", "2H", "ET", "P"}

_TRANSIENT_ERRORS = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.TimeoutException,
)


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


# ── HTTP con reintentos ───────────────────────────────────────────────────────

async def _get_json(url: str, headers: dict, params: dict) -> dict:
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                return resp.json()
        except _TRANSIENT_ERRORS as exc:
            last_exc = exc
            wait = 10 * (attempt + 1)
            print(f"  ⚠ Error de red (intento {attempt+1}/3): {exc!r} — reintentando en {wait}s")
            await asyncio.sleep(wait)
    raise last_exc  # type: ignore[misc]


# ── football-data.org: fixture del día (gratuito) ─────────────────────────────

async def get_fd_schedule() -> list[dict]:
    now = datetime.now(timezone.utc)
    data = await _get_json(
        f"https://api.football-data.org/v4/competitions/{COMPETITION_ID}/matches",
        headers={"X-Auth-Token": FOOTBALL_API_KEY},
        params={
            "dateFrom": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
            "dateTo":   (now + timedelta(days=1)).strftime("%Y-%m-%d"),
        },
    )
    return data.get("matches", [])


def in_match_window(fd_matches: list[dict]) -> bool:
    """¿Hay algún partido cuya ventana (−10 min, +3h45) incluya este momento?"""
    now = datetime.now(timezone.utc)
    for m in fd_matches:
        try:
            kickoff = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if kickoff - timedelta(minutes=10) <= now <= kickoff + timedelta(hours=3, minutes=45):
            return True
    return False


# ── API-Football: partidos en vivo ────────────────────────────────────────────

async def get_af_live() -> list[dict]:
    data = await _get_json(
        f"{AF_BASE}/fixtures",
        headers={"x-apisports-key": API_FOOTBALL_KEY},
        params={"live": "all", "league": AF_LEAGUE, "season": AF_SEASON},
    )
    errors = data.get("errors")
    if errors:
        print(f"  ⚠ API-Football devolvió errores: {errors}", file=sys.stderr)
    return data.get("response", [])


# ── Mapeo API-Football → ids de football-data ────────────────────────────────

def _tokens(s: str) -> set[str]:
    return set((s or "").lower().replace("-", " ").split())


def map_af_to_fd(af_fixture: dict, fd_matches: list[dict]) -> str | None:
    """Encuentra el id de football-data del fixture de API-Football,
    por horario de inicio (±20 min) y similitud de nombres."""
    try:
        af_kickoff = datetime.fromisoformat(af_fixture["fixture"]["date"])
    except (KeyError, ValueError):
        return None
    af_names = (_tokens(af_fixture["teams"]["home"]["name"])
                | _tokens(af_fixture["teams"]["away"]["name"]))

    best_id, best_score = None, -1
    for m in fd_matches:
        try:
            fd_kickoff = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if abs((fd_kickoff - af_kickoff).total_seconds()) > 1200:
            continue
        fd_names = (
            _tokens(m.get("homeTeam", {}).get("name") or "")
            | _tokens(m.get("homeTeam", {}).get("shortName") or "")
            | _tokens(m.get("awayTeam", {}).get("name") or "")
            | _tokens(m.get("awayTeam", {}).get("shortName") or "")
        )
        score = len(af_names & fd_names)
        if score > best_score:
            best_id, best_score = str(m["id"]), score
    return best_id


# ── Estado, cuota y snapshot en Firestore ─────────────────────────────────────

def load_state(db: firestore.Client) -> dict:
    doc = db.collection("notifier_state").document("matches").get()
    return doc.to_dict() if doc.exists else {}


def save_state(db: firestore.Client, state: dict) -> None:
    db.collection("notifier_state").document("matches").set(state)


def check_budget(db: firestore.Client) -> bool:
    """True si queda cuota diaria de API-Football. Incrementa el contador."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ref = db.collection("notifier_state").document("usage")
    doc = ref.get()
    data = doc.to_dict() if doc.exists else {}
    count = data.get("count", 0) if data.get("date") == today else 0
    if count >= AF_DAILY_BUDGET:
        print(f"⛔ Cuota diaria de API-Football agotada ({count}/{AF_DAILY_BUDGET}).")
        return False
    ref.set({"date": today, "count": count + 1})
    return True


def save_snapshot(db: firestore.Client, snapshot: dict) -> None:
    db.collection("notifier_state").document("live_snapshot").set({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "matches": snapshot,
    })


# ── Detección de eventos ──────────────────────────────────────────────────────

def detect_events(prev: dict, curr: dict) -> list[tuple[str, str]]:
    """Retorna lista de (titulo, cuerpo) comparando estado previo y actual."""
    events: list[tuple[str, str]] = []
    home, away = curr["home_name"], curr["away_name"]
    ch, ca = curr.get("home") or 0, curr.get("away") or 0
    ps, cs = prev.get("status", ""), curr["status"]

    if ps in ("NS", "") and cs in _LIVE_SHORTS:
        events.append(("▶️ Inicio del partido", f"{home} vs {away}"))
    elif ps in ("1H", "2H", "ET", "P") and cs == "HT":
        ph, pa = prev.get("home") or 0, prev.get("away") or 0
        events.append(("⏸ Medio tiempo", f"{home} {ph} – {pa} {away}"))
    elif ps in _LIVE_SHORTS and cs == "FT":
        events.append(("🏁 Partido finalizado", f"{home} {ch} – {ca} {away}"))

    if prev and ps not in ("NS", ""):
        ph, pa = prev.get("home") or 0, prev.get("away") or 0
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
    if not API_FOOTBALL_KEY:
        print("ERROR: API_FOOTBALL_KEY no configurado.", file=sys.stderr)
        sys.exit(1)
    if not FOOTBALL_API_KEY:
        print("ERROR: FOOTBALL_API_KEY no configurado.", file=sys.stderr)
        sys.exit(1)

    db = init_firebase()

    print("📅 Consultando fixture (football-data)...")
    try:
        fd_matches = await get_fd_schedule()
    except Exception as e:
        print(f"ERROR consultando fixture: {e!r}", file=sys.stderr)
        sys.exit(0)  # transitorio — no marcar el workflow como fallido

    if not in_match_window(fd_matches):
        print("Fuera de ventana de partidos — sin consumir cuota. Fin.")
        return

    if not check_budget(db):
        return

    print("⚽ Consultando partidos en vivo (API-Football)...")
    try:
        af_live = await get_af_live()
    except Exception as e:
        print(f"ERROR API-Football: {e!r}", file=sys.stderr)
        sys.exit(0)

    print(f"   {len(af_live)} partido(s) en vivo")

    prev_state = load_state(db)
    new_state  = dict(prev_state)
    snapshot: dict = {}
    total_events = 0
    seen_ids: set[str] = set()

    for fx in af_live:
        fd_id = map_af_to_fd(fx, fd_matches)
        if fd_id is None:
            print(f"  ⚠ Sin mapeo fd para {fx['teams']['home']['name']} vs {fx['teams']['away']['name']}")
            continue
        seen_ids.add(fd_id)

        status = _AF_STATUS_NORM.get(fx["fixture"]["status"]["short"], "NS")
        curr = {
            "status":    status,
            "minute":    fx["fixture"]["status"].get("elapsed"),
            "home":      fx["goals"]["home"],
            "away":      fx["goals"]["away"],
            "home_name": fx["teams"]["home"]["name"],
            "away_name": fx["teams"]["away"]["name"],
        }

        for title, body in detect_events(prev_state.get(fd_id, {}), curr):
            print(f"  📣 {title}")
            send_notification(title, body, fd_id)
            total_events += 1

        new_state[fd_id] = {k: v for k, v in curr.items()
                            if k not in ("home_name", "away_name")} | {
            "home_name": curr["home_name"], "away_name": curr["away_name"],
        }
        snapshot[fd_id] = {
            "status": status,
            "minute": curr["minute"],
            "home":   curr["home"],
            "away":   curr["away"],
        }

    # Partidos que estaban en vivo y desaparecieron del feed → finalizados
    for mid, st in prev_state.items():
        if mid in seen_ids or not isinstance(st, dict):
            continue
        if st.get("status") in _LIVE_SHORTS:
            h, a = st.get("home") or 0, st.get("away") or 0
            home = st.get("home_name", "Local")
            away = st.get("away_name", "Visitante")
            print("  📣 🏁 Partido finalizado (salió del feed en vivo)")
            send_notification("🏁 Partido finalizado", f"{home} {h} – {a} {away}", mid)
            total_events += 1
            new_state[mid] = {**st, "status": "FT"}
            snapshot[mid] = {"status": "FT", "minute": None, "home": h, "away": a}

    save_state(db, new_state)
    save_snapshot(db, snapshot)
    print(f"\n✅ {total_events} evento(s) enviado(s). Estado y snapshot guardados.")


if __name__ == "__main__":
    asyncio.run(main())
