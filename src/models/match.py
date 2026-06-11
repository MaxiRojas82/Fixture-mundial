from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MatchStatus(Enum):
    SCHEDULED = "NS"
    LIVE_1H = "1H"
    HALFTIME = "HT"
    LIVE_2H = "2H"
    EXTRA_TIME = "ET"
    PENALTY = "P"
    FINISHED = "FT"
    POSTPONED = "PST"
    CANCELLED = "CANC"

    @classmethod
    def from_short(cls, short: str) -> "MatchStatus":
        for member in cls:
            if member.value == short:
                return member
        return cls.SCHEDULED


LIVE_STATUSES = {
    MatchStatus.LIVE_1H,
    MatchStatus.HALFTIME,
    MatchStatus.LIVE_2H,
    MatchStatus.EXTRA_TIME,
    MatchStatus.PENALTY,
}


@dataclass
class Team:
    id: int
    name: str
    logo: str


@dataclass
class Score:
    home: int | None
    away: int | None


@dataclass
class MatchEvent:
    time: int
    team_id: int
    player: str
    type: str    # "Goal", "Card", "subst"
    detail: str  # "Normal Goal", "Penalty", "Yellow Card", etc.


@dataclass
class Match:
    id: int
    home: Team
    away: Team
    date: datetime
    status: MatchStatus
    score: Score
    elapsed: int | None
    group: str
    events: list[MatchEvent] = field(default_factory=list)
    venue: str = ""

    @property
    def is_live(self) -> bool:
        return self.status in LIVE_STATUSES

    @property
    def display_minute(self) -> int | None:
        """Minuto del API si viene; sino estimado desde el inicio (el plan
        gratuito de football-data.org no envía `minute`)."""
        if self.elapsed:
            return self.elapsed
        if not self.is_live:
            return None
        try:
            mins = int((datetime.now(timezone.utc) - self.date).total_seconds() // 60)
        except TypeError:
            return None
        if mins > 60:  # descontar el entretiempo aproximado
            mins -= 15
        return max(1, min(mins, 120))

    @property
    def score_display(self) -> str:
        h = "-" if self.score.home is None else str(self.score.home)
        a = "-" if self.score.away is None else str(self.score.away)
        return f"{h}  -  {a}"
