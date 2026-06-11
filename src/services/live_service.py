import asyncio
import json
import os
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable
from dotenv import load_dotenv
from src.api.football_client import FootballClient
from src.models.match import Match, MatchStatus, Score, LIVE_STATUSES
from src.models.standing import TeamStanding
from src.services import live_snapshot

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
            # Consultar primero, dormir después — así el primer poll es inmediato
            try:
                await self._fetch_live()
            except Exception:
                pass

            now = datetime.now(timezone.utc)
            live = [m for m in self._matches.values() if m.is_live]
            # Partidos que ya deberían haber empezado según su horario pero
            # siguen "programados" (la API a veces tarda en reflejarlo)
            in_window = [
                m for m in self._matches.values()
                if m.status == MatchStatus.SCHEDULED
                and m.date <= now <= m.date + timedelta(hours=3)
            ]
            if live or in_window:
                sleep_secs = POLL_INTERVAL
            else:
                # Sin partidos en curso → dormir hasta 2 min antes del próximo
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

    # Orden de progreso de un partido — nunca retroceder de estado
    # (football-data a veces vuelve a reportar TIMED un partido ya iniciado)
    @staticmethod
    def _status_order(status: MatchStatus) -> int:
        if status == MatchStatus.FINISHED:
            return 2
        if status in LIVE_STATUSES:
            return 1
        return 0

    def _merge_snapshot(self, snap: dict[int, dict]) -> None:
        """Aplica el snapshot del notificador (API-Football vía Firestore)."""
        for mid, s in snap.items():
            local = self._matches.get(mid)
            if not local:
                continue
            status = MatchStatus.from_short(str(s.get("status") or "NS"))
            if self._status_order(status) < self._status_order(local.status):
                continue
            minute = s.get("minute")
            sh, sa = s.get("home"), s.get("away")
            new_score = Score(
                home=sh if sh is not None else local.score.home,
                away=sa if sa is not None else local.score.away,
            )
            if (status == local.status and minute == local.elapsed
                    and new_score == local.score):
                continue
            prev = local
            current = replace(local, status=status, elapsed=minute, score=new_score)
            self._matches[mid] = current
            self._detect_events(prev, current)
            # Goles sin detalle de eventos: detectar por diferencia de marcador
            ph, pa = prev.score.home or 0, prev.score.away or 0
            ch, ca = current.score.home or 0, current.score.away or 0
            if prev.status != MatchStatus.SCHEDULED:
                marcador = f"{current.home.name} {ch} - {ca} {current.away.name}"
                if ch > ph:
                    self._fire_event(current, f"⚽  GOL de {current.home.name} — {marcador}", "goal")
                if ca > pa:
                    self._fire_event(current, f"⚽  GOL de {current.away.name} — {marcador}", "goal")

    async def _fetch_live(self) -> None:
        # 1) Snapshot del notificador (API-Football, la fuente más confiable)
        try:
            snap = await live_snapshot.fetch()
            if snap:
                self._merge_snapshot(snap)
        except Exception:
            pass

        # 2) football-data directo (gratuito; a veces tarda o retrocede)
        try:
            live_matches = await self._client.get_live_fixtures()
        except Exception:
            self._notify_update()
            return
        current_live_ids: set[int] = set()

        for m in live_matches:
            current_live_ids.add(m.id)
            prev = self._matches.get(m.id)
            if prev and self._status_order(m.status) < self._status_order(prev.status):
                continue
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
