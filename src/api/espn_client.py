"""Cliente del scoreboard público de ESPN — marcador en vivo del Mundial.

No requiere clave ni tiene cuota. Se usa como fuente principal de datos
en vivo porque football-data.org (gratuito) es inestable para esta
competición y API-Football no cubre 2026 en su plan gratuito.
"""

import httpx
from datetime import datetime

_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"


def _parse_minute(clock: str) -> int | None:
    """'45'+4'' → 45 ; '67'' → 67 ; '0'' → None"""
    try:
        base = clock.split("'")[0].strip()
        minute = int(base)
        return minute if minute > 0 else None
    except (ValueError, AttributeError, IndexError):
        return None


def _parse_details(comp: dict, home_team_id: str) -> list[dict]:
    """Goles y tarjetas con jugador, desde competitions[].details."""
    events: list[dict] = []
    for d in comp.get("details", []) or []:
        dtype = ((d.get("type") or {}).get("text") or "")
        athletes = d.get("athletesInvolved") or []
        player = (athletes[0] or {}).get("displayName") or "" if athletes else ""
        team_id = str((d.get("team") or {}).get("id") or "")
        minute = _parse_minute(((d.get("clock") or {}).get("displayValue") or "")) or 0
        side = "home" if team_id == home_team_id else "away"

        if d.get("scoringPlay"):
            low = dtype.lower()
            detail = ("Penalty" if "penalty" in low
                      else "Own Goal" if "own" in low
                      else "Normal Goal")
            assist = (athletes[1] or {}).get("displayName") or "" if len(athletes) > 1 else ""
            events.append({"minute": minute, "side": side, "player": player,
                          "assist": assist, "type": "Goal", "detail": detail})
        elif d.get("redCard"):
            events.append({"minute": minute, "side": side, "player": player,
                          "type": "Card", "detail": "Red Card"})
        elif d.get("yellowCard"):
            events.append({"minute": minute, "side": side, "player": player,
                          "type": "Card", "detail": "Yellow Card"})
    return events


def _score(comp_team: dict) -> int | None:
    raw = comp_team.get("score")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def _fetch_and_parse(
    params: dict | None = None,
    states: set[str] | None = None,
) -> list[dict]:
    """Descarga el scoreboard de ESPN y parsea todos los partidos.

    states — si se pasa, filtra por state (e.g. {"in", "post"}); None = todos.
    """
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(_URL, params=params or {})
        r.raise_for_status()
        data = r.json()

    out: list[dict] = []
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        stype = (ev.get("status") or {}).get("type") or {}
        state = stype.get("state")
        if states is not None and state not in states:
            continue

        try:
            kickoff = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue

        home_c, away_c = None, None
        for comp_team in comp.get("competitors", []):
            if comp_team.get("homeAway") == "home":
                home_c = comp_team
            elif comp_team.get("homeAway") == "away":
                away_c = comp_team
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

        home_team_id = str((home_c.get("team") or {}).get("id") or "")
        out.append({
            "kickoff":    kickoff,
            "home":       (home_c.get("team") or {}).get("displayName") or "",
            "away":       (away_c.get("team") or {}).get("displayName") or "",
            "status":     short,
            "minute":     _parse_minute((ev.get("status") or {}).get("displayClock") or ""),
            "home_goals": _score(home_c),
            "away_goals": _score(away_c),
            "events":     _parse_details(comp, home_team_id),
        })
    return out


async def get_live() -> list[dict]:
    """Partidos en juego o recién terminados, según ESPN."""
    return await _fetch_and_parse(states={"in", "post"})


async def get_by_date(date_str: str) -> list[dict]:
    """Partidos de una fecha específica (YYYYMMDD). Solo finalizados (post).

    Útil para recuperar eventos históricos de partidos ya terminados que
    ya no aparecen en el scoreboard en vivo.
    """
    return await _fetch_and_parse(params={"dates": date_str}, states={"post"})
