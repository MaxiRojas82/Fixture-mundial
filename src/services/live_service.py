import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable
from dotenv import load_dotenv
from src.api.football_client import FootballClient
from src.models.match import Match, MatchStatus, LIVE_STATUSES
from src.models.standing import TeamStanding

load_dotenv()

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
CACHE_DIR = Path("cache")
CACHE_TTL = timedelta(hours=1)

GoalCallback  = Callable[[Match, str], None]
UpdateCallback = Callable[[], None]
EventCallback  = Callable[[Match, str, str], None]  # match, text, event_type

_LIVE_PLAYING = {
    MatchStatus.LIVE_1H,
    MatchStatus.LIVE_2H,
    MatchStatus.EXTRA_TIME,
    MatchStatus.PENALTY,
}


class LiveService:
    def __init__(self) -> None:
        self._client = FootballClient()
        self._matches: dict[int, Match] = {}
        self._standings: list[TeamStanding] = []
        self._goal_callbacks: list[GoalCallback] = []
        self._update_callbacks: list[UpdateCallback] = []
        self._event_callbacks: list[EventCallback] = []
        self._prev_live_ids: set[int] = set()
        self._running = False
        self._task: asyncio.Task | None = None
        self._load_error: str = ""

    # ── Subscripción de callbacks ──────────────────────────────────────────

    def on_goal(self, callback: GoalCallback) -> None:
        if callback not in self._goal_callbacks:
            self._goal_callbacks.append(callback)

    def on_update(self, callback: UpdateCallback) -> None:
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)
            if self._standings or self._matches:
                try:
                    callback()
                except Exception:
                    pass

    def on_event(self, callback: EventCallback) -> None:
        if callback not in self._event_callbacks:
            self._event_callbacks.append(callback)

    # ── Propiedades de estado ──────────────────────────────────────────────

    @property
    def matches(self) -> list[Match]:
        return sorted(self._matches.values(), key=lambda m: m.date)

    @property
    def live_matches(self) -> list[Match]:
        return [m for m in self._matches.values() if m.is_live]

    @property
    def standings(self) -> list[TeamStanding]:
        return self._standings

    async def get_match(self, match_id: int) -> Match | None:
        if match_id in self._matches:
            return self._matches[match_id]
        match = await self._client.get_match(match_id)
        if match:
            self._matches[match.id] = match
        return match

    # ── Ciclo de vida ──────────────────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        await self._fetch_all()
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def refresh(self) -> None:
        """Fuerza recarga completa ignorando caché."""
        await self._fetch_all(force=True)

    # ── Lógica interna ─────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        while self._running:
            live = [m for m in self._matches.values() if m.status in _LIVE_PLAYING]
            if live:
                # Hay partidos en curso → poll frecuente
                await asyncio.sleep(POLL_INTERVAL)
            else:
                # Sin partidos en vivo → dormir hasta 2 min antes del próximo
                now = datetime.now(timezone.utc)
                upcoming = [
                    m for m in self._matches.values()
                    if m.status == MatchStatus.SCHEDULED and m.date > now
                ]
                if upcoming:
                    nxt = min(upcoming, key=lambda m: m.date)
                    secs = (nxt.date - now).total_seconds() - 120
                    sleep_secs = max(POLL_INTERVAL, min(secs, 1800))
                else:
                    sleep_secs = 1800  # 30 min si no hay más partidos
                await asyncio.sleep(sleep_secs)
            try:
                await self._fetch_live()
            except Exception:
                pass

    @property
    def load_error(self) -> str:
        return self._load_error

    # ── Caché en disco ─────────────────────────────────────────────────────

    @staticmethod
    def _load_from_cache(path: Path, ignore_ttl: bool = False) -> dict | None:
        try:
            if not path.exists():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            if not ignore_ttl:
                saved_at = datetime.fromisoformat(data["saved_at"])
                if datetime.now(timezone.utc) - saved_at > CACHE_TTL:
                    return None
            return data["payload"]
        except Exception:
            return None

    @staticmethod
    def _save_to_cache(path: Path, payload: dict) -> None:
        try:
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps({
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    async def _fetch_all(self, force: bool = False) -> None:
        try:
            from src.ui.flags import prefetch_flags

            fixtures_raw = None if force else self._load_from_cache(CACHE_DIR / "fixtures.json")
            standings_raw = None if force else self._load_from_cache(CACHE_DIR / "standings.json")

            if fixtures_raw is None:
                fixtures_raw = await self._client.get_fixtures_raw()
                self._save_to_cache(CACHE_DIR / "fixtures.json", fixtures_raw)

            if standings_raw is None:
                standings_raw = await self._client.get_standings_raw()
                self._save_to_cache(CACHE_DIR / "standings.json", standings_raw)

            matches = self._client.parse_fixtures(fixtures_raw)
            for m in matches:
                self._matches[m.id] = m
            self._standings = self._client.parse_standings(standings_raw)

            team_names = list({
                m.home.name for m in matches if m.home.id != 0
            } | {
                m.away.name for m in matches if m.away.id != 0
            })
            await prefetch_flags(team_names)
            self._load_error = ""
            self._notify_update()
        except Exception as e:
            self._load_error = str(e)
            # Fallback: intentar caché stale si no hay datos
            if not self._matches:
                try:
                    stale = self._load_from_cache(CACHE_DIR / "fixtures.json", ignore_ttl=True)
                    if stale:
                        for m in self._client.parse_fixtures(stale):
                            self._matches[m.id] = m
                except Exception:
                    pass
            self._notify_update()

    async def _fetch_live(self) -> None:
        live_matches = await self._client.get_live_fixtures()
        current_live_ids: set[int] = set()

        for m in live_matches:
            current_live_ids.add(m.id)
            prev = self._matches.get(m.id)
            self._matches[m.id] = m
            if prev:
                self._detect_events(prev, m)

        # Partidos que desaparecieron del listado en vivo → probablemente terminaron
        disappeared = self._prev_live_ids - current_live_ids
        for mid in disappeared:
            try:
                refreshed = await self._client.get_match(mid)
                if refreshed and refreshed.status == MatchStatus.FINISHED:
                    prev = self._matches.get(mid)
                    self._matches[mid] = refreshed
                    if prev and prev.status != MatchStatus.FINISHED:
                        h = refreshed.score.home if refreshed.score.home is not None else "?"
                        a = refreshed.score.away if refreshed.score.away is not None else "?"
                        text = f"🏁  Final — {refreshed.home.name} {h} - {a} {refreshed.away.name}"
                        self._fire_event(refreshed, text, "fulltime")
            except Exception:
                pass

        self._prev_live_ids = current_live_ids
        self._notify_update()

    def _detect_events(self, prev: Match, current: Match) -> None:
        # Cambios de estado
        if prev.status == MatchStatus.SCHEDULED and current.status in _LIVE_PLAYING:
            text = f"▶️  Inicio — {current.home.name} vs {current.away.name}"
            self._fire_event(current, text, "kickoff")

        elif prev.status in _LIVE_PLAYING and current.status == MatchStatus.HALFTIME:
            h = current.score.home if current.score.home is not None else "?"
            a = current.score.away if current.score.away is not None else "?"
            text = f"⏸  Medio tiempo — {current.home.name} {h} - {a} {current.away.name}"
            self._fire_event(current, text, "halftime")

        elif (prev.status in _LIVE_PLAYING or prev.status == MatchStatus.HALFTIME) \
                and current.status == MatchStatus.FINISHED:
            h = current.score.home if current.score.home is not None else "?"
            a = current.score.away if current.score.away is not None else "?"
            text = f"🏁  Final — {current.home.name} {h} - {a} {current.away.name}"
            self._fire_event(current, text, "fulltime")

        # Goles nuevos
        prev_goals = {(e.time, e.player) for e in prev.events if e.type == "Goal"}
        for ev in current.events:
            if ev.type != "Goal":
                continue
            if (ev.time, ev.player) not in prev_goals:
                team = current.home.name if ev.team_id == current.home.id else current.away.name
                is_pen = "penalty" in ev.detail.lower()
                if is_pen:
                    text = f"🎯  PENAL — {ev.player} ({team})  {ev.time}'"
                    self._fire_event(current, text, "penalty")
                else:
                    text = f"⚽  GOL — {ev.player} ({team})  {ev.time}'"
                    self._fire_event(current, text, "goal")
                    # mantener compatibilidad con on_goal
                    for cb in self._goal_callbacks:
                        try:
                            cb(current, text)
                        except Exception:
                            pass

        # Tarjetas nuevas
        prev_cards = {(e.time, e.player) for e in prev.events if e.type == "Card"}
        for ev in current.events:
            if ev.type != "Card":
                continue
            if (ev.time, ev.player) not in prev_cards:
                team = current.home.name if ev.team_id == current.home.id else current.away.name
                is_red = "red" in ev.detail.lower()
                if is_red:
                    text = f"🟥  ROJA — {ev.player} ({team})  {ev.time}'"
                    self._fire_event(current, text, "red_card")
                else:
                    text = f"🟨  AMARILLA — {ev.player} ({team})  {ev.time}'"
                    self._fire_event(current, text, "yellow_card")

    def _fire_event(self, match: Match, text: str, event_type: str) -> None:
        from src.ui.notifications import should_notify_match
        if not should_notify_match(match.home.name, match.away.name):
            return
        for cb in self._event_callbacks:
            try:
                cb(match, text, event_type)
            except Exception:
                pass

    def _notify_update(self) -> None:
        for cb in self._update_callbacks:
            try:
                cb()
            except Exception:
                pass
