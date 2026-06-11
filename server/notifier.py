#!/usr/bin/env python3
"""
MaxFixture FCM Notifier — corre cada 5 minutos via GitHub Actions.

Fuente de datos en vivo: scoreboard público de ESPN (sin clave, sin cuota).
football-data.org se usa solo para obtener el fixture y mapear los ids
que usa la app.

Detecta inicio/goles/entretiempo/final comparando contra el estado previo
guardado en Firestore (notifier_state/matches), envía push notifications
por FCM y publica un snapshot en vivo (notifier_state/live_snapshot) que
la app usa como respaldo de datos.
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

FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
COMPETITION_ID   = os.environ.get("WORLD_CUP_COMPETITION_ID", "2000")
FCM_TOPIC        = "maxfixture_events"

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

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

async def _get_json(url: str, headers: dict | None = None, params: dict | None = None) -> dict:
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers or {}, params=params or {})
                resp.raise_for_status()
                return resp.json()
        except _TRANSIENT_ERRORS as exc:
            last_exc = exc
            wait = 10 * (attempt + 1)
            print(f"  ⚠ Error de red (intento {attempt+1}/3): {exc!r} — reintentando en {wait}s")
            await asyncio.sleep(wait)
    raise last_exc  # type: ignore[misc]


# ── football-data.org: fixture para mapear ids (gratuito) ─────────────────────

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


# ── ESPN: partidos en vivo ────────────────────────────────────────────────────

def _parse_minute(clock: str) -> int | None:
    try:
        minute = int(clock.split("'")[0].strip())
        return minute if minute > 0 else None
    except (ValueError, AttributeError, IndexError):
        return None


async def get_espn_live() -> list[dict]:
    data = await _get_json(ESPN_URL)
    out: list[dict] = []
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        stype = (ev.get("status") or {}).get("type") or {}
        state = stype.get("state")
        if state not in ("in", "post"):
            continue
        try:
            kickoff = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue

        home_c, away_c = None, None
        for ct in comp.get("competitors", []):
            if ct.get("homeAway") == "home":
                home_c = ct
            elif ct.get("homeAway") == "away":
                away_c = ct
        if not home_c or not away_c:
            continue

        detail = (stype.get("shortDetail") or "").upper()
        period = (ev.get("status") or {}).get("period") or 1
        if state == "post":
            short = "FT"
        elif "HT" in detail or "HALF" in detail:
            short = "HT"
        elif "PEN" in detail or "SHOOTOUT" in detail:
            short = "P"
        elif period >= 3:
            short = "ET"
        elif period <= 1:
            short = "1H"
        else:
            short = "2H"

        def _score(ct: dict) -> int | None:
            try:
                return int(ct.get("score"))
            except (TypeError, ValueError):
                return None

        # Goleadores por equipo, en orden, desde los detalles del partido
        home_id = str((home_c.get("team") or {}).get("id") or "")
        scorers_home: list[str] = []
        scorers_away: list[str] = []
        for d in comp.get("details", []) or []:
            if not d.get("scoringPlay"):
                continue
            athletes = d.get("athletesInvolved") or []
            player = (athletes[0] or {}).get("displayName") or "" if athletes else ""
            clock = ((d.get("clock") or {}).get("displayValue") or "").strip()
            label = f"{player} {clock}".strip()
            if str((d.get("team") or {}).get("id") or "") == home_id:
                scorers_home.append(label)
            else:
                scorers_away.append(label)

        out.append({
            "kickoff":      kickoff,
            "home_name":    (home_c.get("team") or {}).get("displayName") or "",
            "away_name":    (away_c.get("team") or {}).get("displayName") or "",
            "status":       short,
            "minute":       _parse_minute((ev.get("status") or {}).get("displayClock") or ""),
            "home":         _score(home_c),
            "away":         _score(away_c),
            "scorers_home": scorers_home,
            "scorers_away": scorers_away,
        })
    return out


# ── Mapeo ESPN → ids de football-data ─────────────────────────────────────────

def _tokens(s: str) -> set[str]:
    return set((s or "").lower().replace("-", " ").split())


def map_to_fd_id(kickoff: datetime, home: str, away: str, fd_matches: list[dict]) -> str | None:
    want = _tokens(home) | _tokens(away)
    best_id, best_score = None, 0
    for m in fd_matches:
        try:
            fd_kickoff = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if abs((fd_kickoff - kickoff).total_seconds()) > 1200:
            continue
        fd_names = (
            _tokens(m.get("homeTeam", {}).get("name") or "")
            | _tokens(m.get("homeTeam", {}).get("shortName") or "")
            | _tokens(m.get("awayTeam", {}).get("name") or "")
            | _tokens(m.get("awayTeam", {}).get("shortName") or "")
        )
        score = len(want & fd_names)
        if score > best_score:
            best_id, best_score = str(m["id"]), score
    return best_id


# ── Estado y snapshot en Firestore ────────────────────────────────────────────

def load_state(db: firestore.Client) -> dict:
    doc = db.collection("notifier_state").document("matches").get()
    return doc.to_dict() if doc.exists else {}


def save_state(db: firestore.Client, state: dict) -> None:
    db.collection("notifier_state").document("matches").set(state)


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
        scorers_h = curr.get("scorers_home") or []
        scorers_a = curr.get("scorers_away") or []
        for i in range(max(0, ch - ph)):
            idx = ph + i
            who = f"{scorers_h[idx]} · " if idx < len(scorers_h) else ""
            events.append((f"⚽ ¡GOL de {home}!", f"{who}{home} {ch} – {ca} {away}"))
        for i in range(max(0, ca - pa)):
            idx = pa + i
            who = f"{scorers_a[idx]} · " if idx < len(scorers_a) else ""
            events.append((f"⚽ ¡GOL de {away}!", f"{who}{home} {ch} – {ca} {away}"))

    return events


# ── FCM ───────────────────────────────────────────────────────────────────────

_notif_seq = 0


def send_notification(title: str, body: str, match_id: str) -> None:
    # Tag único por evento: con un tag compartido por partido, Android
    # reemplaza la notificación anterior (el gol pisaba al final, etc.)
    global _notif_seq
    _notif_seq += 1
    msg = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={"matchId": match_id},
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="maxfixture_goals",
                sound="default",
                priority="high",
                icon="ic_stat_notify",
                tag=f"{match_id}_{_notif_seq}_{datetime.now(timezone.utc).strftime('%H%M%S')}",
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

    print("📅 Consultando fixture (football-data)...")
    try:
        fd_matches = await get_fd_schedule()
    except Exception as e:
        print(f"ERROR consultando fixture: {e!r}", file=sys.stderr)
        sys.exit(0)  # transitorio — no marcar el workflow como fallido

    if not in_match_window(fd_matches):
        print("Fuera de ventana de partidos. Fin.")
        return

    print("⚽ Consultando partidos en vivo (ESPN)...")
    try:
        espn_live = await get_espn_live()
    except Exception as e:
        print(f"ERROR ESPN: {e!r}", file=sys.stderr)
        sys.exit(0)

    print(f"   {len(espn_live)} partido(s) en juego o recién terminados")

    prev_state = load_state(db)
    new_state  = dict(prev_state)
    snapshot: dict = {}
    total_events = 0
    seen_ids: set[str] = set()

    for item in espn_live:
        fd_id = map_to_fd_id(item["kickoff"], item["home_name"], item["away_name"], fd_matches)
        if fd_id is None:
            print(f"  ⚠ Sin mapeo fd para {item['home_name']} vs {item['away_name']}")
            continue
        seen_ids.add(fd_id)

        curr = {k: item[k] for k in ("status", "minute", "home", "away",
                                     "home_name", "away_name",
                                     "scorers_home", "scorers_away")}

        for title, body in detect_events(prev_state.get(fd_id) or {}, curr):
            print(f"  📣 {title}")
            send_notification(title, body, fd_id)
            total_events += 1

        new_state[fd_id] = curr
        snapshot[fd_id] = {
            "status": curr["status"],
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
