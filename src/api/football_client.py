import asyncio
import os
import httpx
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from src.models.match import Match, Team, Score, MatchStatus, MatchEvent
from src.models.standing import TeamStanding

load_dotenv()

BASE_URL = "https://api.football-data.org/v4"
COMPETITION_ID = os.getenv("WORLD_CUP_COMPETITION_ID", "2000")

# Venue por match ID para partidos conocidos (fallback si API no devuelve venue).
_WC2026_VENUES: dict[int, str] = {
    # ── Dieciseisavos ─────────────────────────────────────────────────────────
    537417: "SoFi Stadium, Los Ángeles",
    537423: "Gillette Stadium, Boston",
    537415: "Estadio BBVA, Monterrey",
    537418: "NRG Stadium, Houston",
    537424: "MetLife Stadium, New York/NJ",
    537416: "AT&T Stadium, Arlington",
    537425: "Estadio Azteca, Ciudad de México",
    537426: "Mercedes-Benz Stadium, Atlanta",
    537422: "Levi's Stadium, San Francisco",
    537421: "Lumen Field, Seattle",
    537420: "BMO Field, Toronto",
    537419: "SoFi Stadium, Los Ángeles",
    537429: "BC Place, Vancouver",
    537428: "Hard Rock Stadium, Miami",
    537427: "Arrowhead Stadium, Kansas City",
    537430: "AT&T Stadium, Arlington",
}

# Venue por par de equipos — fase de grupos (la API no devuelve venue para estos partidos)
_WC2026_PAIR_VENUES: dict[frozenset, str] = {
    # Grupo A: México · Sudáfrica · Corea del Sur · Rep. Checa
    frozenset({"Mexico", "South Africa"}):            "Estadio Azteca, Ciudad de México",
    frozenset({"Korea Republic", "Czech Republic"}):  "Estadio Akron, Guadalajara",
    frozenset({"Korea Republic", "Czechia"}):         "Estadio Akron, Guadalajara",
    frozenset({"Czech Republic", "South Africa"}):    "Mercedes-Benz Stadium, Atlanta",
    frozenset({"Czechia", "South Africa"}):           "Mercedes-Benz Stadium, Atlanta",
    frozenset({"Mexico", "Korea Republic"}):          "Estadio Akron, Guadalajara",
    frozenset({"South Africa", "Korea Republic"}):    "Estadio BBVA, Monterrey",
    frozenset({"Czech Republic", "Mexico"}):          "Estadio Azteca, Ciudad de México",
    frozenset({"Czechia", "Mexico"}):                 "Estadio Azteca, Ciudad de México",
    # Grupo B: Canadá · Bosnia-Herzegovina · Catar · Suiza
    frozenset({"Canada", "Bosnia and Herzegovina"}):  "BMO Field, Toronto",
    frozenset({"Canada", "Bosnia-Herzegovina"}):      "BMO Field, Toronto",
    frozenset({"Canada", "Bosnia-H."}):               "BMO Field, Toronto",
    frozenset({"Qatar", "Switzerland"}):              "Levi's Stadium, San Francisco",
    frozenset({"Switzerland", "Bosnia and Herzegovina"}): "SoFi Stadium, Los Ángeles",
    frozenset({"Switzerland", "Bosnia-Herzegovina"}): "SoFi Stadium, Los Ángeles",
    frozenset({"Switzerland", "Bosnia-H."}):          "SoFi Stadium, Los Ángeles",
    frozenset({"Canada", "Qatar"}):                   "BC Place, Vancouver",
    frozenset({"Bosnia and Herzegovina", "Qatar"}):   "Lumen Field, Seattle",
    frozenset({"Bosnia-Herzegovina", "Qatar"}):       "Lumen Field, Seattle",
    frozenset({"Bosnia-H.", "Qatar"}):                "Lumen Field, Seattle",
    frozenset({"Switzerland", "Canada"}):             "BC Place, Vancouver",
    # Grupo C: Brasil · Marruecos · Haití · Escocia
    frozenset({"Brazil", "Morocco"}):                 "MetLife Stadium, New York/NJ",
    frozenset({"Haiti", "Scotland"}):                 "Gillette Stadium, Boston",
    frozenset({"Scotland", "Morocco"}):               "Gillette Stadium, Boston",
    frozenset({"Brazil", "Haiti"}):                   "Lincoln Financial Field, Philadelphia",
    frozenset({"Morocco", "Haiti"}):                  "Mercedes-Benz Stadium, Atlanta",
    frozenset({"Scotland", "Brazil"}):                "Hard Rock Stadium, Miami",
    # Grupo D: EE.UU. · Paraguay · Australia · Turquía
    frozenset({"United States", "Paraguay"}):         "SoFi Stadium, Los Ángeles",
    frozenset({"USA", "Paraguay"}):                   "SoFi Stadium, Los Ángeles",
    frozenset({"Australia", "Turkey"}):               "BC Place, Vancouver",
    frozenset({"Australia", "Türkiye"}):              "BC Place, Vancouver",
    frozenset({"United States", "Australia"}):        "Lumen Field, Seattle",
    frozenset({"USA", "Australia"}):                  "Lumen Field, Seattle",
    frozenset({"Turkey", "Paraguay"}):                "Levi's Stadium, San Francisco",
    frozenset({"Türkiye", "Paraguay"}):               "Levi's Stadium, San Francisco",
    frozenset({"Turkey", "United States"}):           "SoFi Stadium, Los Ángeles",
    frozenset({"Türkiye", "United States"}):          "SoFi Stadium, Los Ángeles",
    frozenset({"Turkey", "USA"}):                     "SoFi Stadium, Los Ángeles",
    frozenset({"Türkiye", "USA"}):                    "SoFi Stadium, Los Ángeles",
    frozenset({"Paraguay", "Australia"}):             "Levi's Stadium, San Francisco",
    # Grupo E: Alemania · Curazao · Costa de Marfil · Ecuador
    frozenset({"Germany", "Curaçao"}):                "NRG Stadium, Houston",
    frozenset({"Germany", "Curacao"}):                "NRG Stadium, Houston",
    frozenset({"Côte d'Ivoire", "Ecuador"}):          "Lincoln Financial Field, Philadelphia",
    frozenset({"Cote d'Ivoire", "Ecuador"}):          "Lincoln Financial Field, Philadelphia",
    frozenset({"Ivory Coast", "Ecuador"}):            "Lincoln Financial Field, Philadelphia",
    frozenset({"Germany", "Côte d'Ivoire"}):          "BMO Field, Toronto",
    frozenset({"Germany", "Cote d'Ivoire"}):          "BMO Field, Toronto",
    frozenset({"Germany", "Ivory Coast"}):            "BMO Field, Toronto",
    frozenset({"Ecuador", "Curaçao"}):                "Arrowhead Stadium, Kansas City",
    frozenset({"Ecuador", "Curacao"}):                "Arrowhead Stadium, Kansas City",
    frozenset({"Ecuador", "Germany"}):                "MetLife Stadium, New York/NJ",
    frozenset({"Curaçao", "Côte d'Ivoire"}):          "Lincoln Financial Field, Philadelphia",
    frozenset({"Curaçao", "Cote d'Ivoire"}):          "Lincoln Financial Field, Philadelphia",
    frozenset({"Curaçao", "Ivory Coast"}):            "Lincoln Financial Field, Philadelphia",
    frozenset({"Curacao", "Côte d'Ivoire"}):          "Lincoln Financial Field, Philadelphia",
    frozenset({"Curacao", "Cote d'Ivoire"}):          "Lincoln Financial Field, Philadelphia",
    frozenset({"Curacao", "Ivory Coast"}):            "Lincoln Financial Field, Philadelphia",
    # Grupo F: Países Bajos · Japón · Suecia · Túnez
    frozenset({"Netherlands", "Japan"}):              "AT&T Stadium, Arlington",
    frozenset({"Sweden", "Tunisia"}):                 "Estadio BBVA, Monterrey",
    frozenset({"Netherlands", "Sweden"}):             "NRG Stadium, Houston",
    frozenset({"Tunisia", "Japan"}):                  "Estadio BBVA, Monterrey",
    frozenset({"Japan", "Sweden"}):                   "AT&T Stadium, Arlington",
    frozenset({"Tunisia", "Netherlands"}):            "Arrowhead Stadium, Kansas City",
    # Grupo G: Bélgica · Egipto · Irán · Nueva Zelanda
    frozenset({"Belgium", "Egypt"}):                  "Lumen Field, Seattle",
    frozenset({"Iran", "New Zealand"}):               "SoFi Stadium, Los Ángeles",
    frozenset({"Belgium", "Iran"}):                   "SoFi Stadium, Los Ángeles",
    frozenset({"New Zealand", "Egypt"}):              "BC Place, Vancouver",
    frozenset({"Egypt", "Iran"}):                     "Lumen Field, Seattle",
    frozenset({"New Zealand", "Belgium"}):            "BC Place, Vancouver",
    # Grupo H: España · Cabo Verde · Arabia Saudita · Uruguay
    frozenset({"Spain", "Cabo Verde"}):               "Mercedes-Benz Stadium, Atlanta",
    frozenset({"Spain", "Cape Verde"}):               "Mercedes-Benz Stadium, Atlanta",
    frozenset({"Saudi Arabia", "Uruguay"}):           "Hard Rock Stadium, Miami",
    frozenset({"Spain", "Saudi Arabia"}):             "Mercedes-Benz Stadium, Atlanta",
    frozenset({"Uruguay", "Cabo Verde"}):             "Hard Rock Stadium, Miami",
    frozenset({"Uruguay", "Cape Verde"}):             "Hard Rock Stadium, Miami",
    frozenset({"Cabo Verde", "Saudi Arabia"}):        "NRG Stadium, Houston",
    frozenset({"Cape Verde", "Saudi Arabia"}):        "NRG Stadium, Houston",
    frozenset({"Uruguay", "Spain"}):                  "Estadio Akron, Guadalajara",
    # Grupo I: Francia · Senegal · Irak · Noruega
    frozenset({"France", "Senegal"}):                 "MetLife Stadium, New York/NJ",
    frozenset({"Iraq", "Norway"}):                    "Gillette Stadium, Boston",
    frozenset({"France", "Iraq"}):                    "Lincoln Financial Field, Philadelphia",
    frozenset({"Norway", "Senegal"}):                 "MetLife Stadium, New York/NJ",
    frozenset({"Norway", "France"}):                  "Gillette Stadium, Boston",
    frozenset({"Senegal", "Iraq"}):                   "BMO Field, Toronto",
    # Grupo J: Argentina · Argelia · Austria · Jordania
    frozenset({"Argentina", "Algeria"}):              "Arrowhead Stadium, Kansas City",
    frozenset({"Austria", "Jordan"}):                 "Levi's Stadium, San Francisco",
    frozenset({"Argentina", "Austria"}):              "AT&T Stadium, Arlington",
    frozenset({"Jordan", "Algeria"}):                 "Levi's Stadium, San Francisco",
    frozenset({"Algeria", "Austria"}):                "Arrowhead Stadium, Kansas City",
    frozenset({"Jordan", "Argentina"}):               "AT&T Stadium, Arlington",
    # Grupo K: Portugal · Congo DR · Uzbekistán · Colombia
    frozenset({"Portugal", "Congo DR"}):              "NRG Stadium, Houston",
    frozenset({"Portugal", "DR Congo"}):              "NRG Stadium, Houston",
    frozenset({"Uzbekistan", "Colombia"}):            "Estadio Azteca, Ciudad de México",
    frozenset({"Portugal", "Uzbekistan"}):            "NRG Stadium, Houston",
    frozenset({"Colombia", "Congo DR"}):              "Estadio Akron, Guadalajara",
    frozenset({"Colombia", "DR Congo"}):              "Estadio Akron, Guadalajara",
    frozenset({"Colombia", "Portugal"}):              "Hard Rock Stadium, Miami",
    frozenset({"Congo DR", "Uzbekistan"}):            "Mercedes-Benz Stadium, Atlanta",
    frozenset({"DR Congo", "Uzbekistan"}):            "Mercedes-Benz Stadium, Atlanta",
    # Grupo L: Inglaterra · Croacia · Ghana · Panamá
    frozenset({"England", "Croatia"}):                "AT&T Stadium, Arlington",
    frozenset({"Ghana", "Panama"}):                   "BMO Field, Toronto",
    frozenset({"England", "Ghana"}):                  "Gillette Stadium, Boston",
    frozenset({"Panama", "Croatia"}):                 "BMO Field, Toronto",
    frozenset({"Panama", "England"}):                 "MetLife Stadium, New York/NJ",
    frozenset({"Croatia", "Ghana"}):                  "Lincoln Financial Field, Philadelphia",
}

# Bracket oficial FIFA Mundial 2026 — mapeado verificando horarios UTC vs sede.
# El API devuelve null para todos los equipos TBD en eliminatorias.
_WC2026_BRACKET: dict[int, tuple[str, str]] = {
    # ── Dieciseisavos de Final (Last 32) ──────────────────────────────────
    537417: ("2° Grupo A",  "2° Grupo B"),            # M73  Jun 28 SoFi (LA)
    537423: ("1° Grupo E",  "Mejor 3° Clasificado"),  # M74  Jun 29 Gillette (Boston)
    537415: ("1° Grupo F",  "2° Grupo C"),            # M75  Jun 29 Estadio BBVA (Guadalupe)
    537418: ("1° Grupo C",  "2° Grupo F"),            # M76  Jun 29→30 UTC NRG (Houston)
    537424: ("1° Grupo I",  "Mejor 3° Clasificado"),  # M77  Jun 30 MetLife (NJ)
    537416: ("2° Grupo E",  "2° Grupo I"),            # M78  Jun 30 AT&T (Arlington)
    537425: ("1° Grupo A",  "Mejor 3° Clasificado"),  # M79  Jun 30→Jul 1 UTC Azteca
    537426: ("1° Grupo L",  "Mejor 3° Clasificado"),  # M80  Jul 1  Mercedes-Benz (Atlanta)
    537422: ("1° Grupo D",  "Mejor 3° Clasificado"),  # M81  Jul 1  Levi's (Santa Clara)
    537421: ("1° Grupo G",  "Mejor 3° Clasificado"),  # M82  Jul 1→2 UTC Lumen (Seattle)
    537420: ("2° Grupo K",  "2° Grupo L"),            # M83  Jul 2  BMO (Toronto)
    537419: ("1° Grupo H",  "2° Grupo J"),            # M84  Jul 2  SoFi (LA)
    537429: ("1° Grupo B",  "Mejor 3° Clasificado"),  # M85  Jul 2→3 UTC BC Place (Vancouver)
    537428: ("1° Grupo J",  "2° Grupo H"),            # M86  Jul 3  Hard Rock (Miami)
    537427: ("1° Grupo K",  "Mejor 3° Clasificado"),  # M87  Jul 3  Arrowhead (KC)
    537430: ("2° Grupo D",  "2° Grupo G"),            # M88  Jul 3→4 UTC AT&T (Arlington)
    # ── Octavos de Final (Last 16) ────────────────────────────────────────
    537376: ("Gan. (2°A/2°B)",  "Gan. (1°E/3°)"),     # Oct.1  Jul 4 17:00
    537375: ("Gan. (1°F/2°C)",  "Gan. (1°C/2°F)"),    # Oct.2  Jul 4 21:00
    537377: ("Gan. (1°I/3°)",   "Gan. (2°E/2°I)"),    # Oct.3  Jul 5 20:00
    537378: ("Gan. (1°A/3°)",   "Gan. (1°L/3°)"),     # Oct.4  Jul 6 00:00
    537379: ("Gan. (1°D/3°)",   "Gan. (1°G/3°)"),     # Oct.5  Jul 6 19:00
    537380: ("Gan. (2°K/2°L)",  "Gan. (1°H/2°J)"),    # Oct.6  Jul 7 00:00
    537381: ("Gan. (1°B/3°)",   "Gan. (1°J/2°H)"),    # Oct.7  Jul 7 16:00
    537382: ("Gan. (1°K/3°)",   "Gan. (2°D/2°G)"),    # Oct.8  Jul 7 20:00
    # ── Cuartos de Final ──────────────────────────────────────────────────
    537383: ("Gan. Oct.1",  "Gan. Oct.2"),             # Cto.1  Jul 9
    537384: ("Gan. Oct.3",  "Gan. Oct.4"),             # Cto.2  Jul 10
    537385: ("Gan. Oct.5",  "Gan. Oct.6"),             # Cto.3  Jul 11
    537386: ("Gan. Oct.7",  "Gan. Oct.8"),             # Cto.4  Jul 12
    # ── Semifinales ───────────────────────────────────────────────────────
    537387: ("Gan. Cto.1",  "Gan. Cto.2"),             # Semi 1  Jul 14
    537388: ("Gan. Cto.3",  "Gan. Cto.4"),             # Semi 2  Jul 15
    # ── Tercer y Cuarto Puesto ────────────────────────────────────────────
    537389: ("Per. Semi 1", "Per. Semi 2"),             # Jul 18
    # ── Final ─────────────────────────────────────────────────────────────
    537390: ("Gan. Semi 1", "Gan. Semi 2"),             # Jul 19
}

# football-data.org status → MatchStatus interno
_STATUS_MAP: dict[str, MatchStatus] = {
    "SCHEDULED": MatchStatus.SCHEDULED,
    "TIMED":     MatchStatus.SCHEDULED,
    "IN_PLAY":   MatchStatus.LIVE_1H,
    "PAUSED":    MatchStatus.HALFTIME,
    "FINISHED":  MatchStatus.FINISHED,
    "SUSPENDED": MatchStatus.POSTPONED,
    "POSTPONED": MatchStatus.POSTPONED,
    "CANCELLED": MatchStatus.CANCELLED,
    "LIVE":      MatchStatus.LIVE_1H,
}


class FootballClient:
    def __init__(self) -> None:
        self._headers = {"X-Auth-Token": os.getenv("FOOTBALL_API_KEY", "5018923c1990450b857203682e1476e6")}

    # ── HTTP con retry en 429 ─────────────────────────────────────────────

    async def _get(self, url: str, params: dict | None = None) -> dict:
        """GET con retry automático: espera Retry-After (mín 65s) en 429."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(3):
                r = await client.get(url, headers=self._headers, params=params or {})
                if r.status_code == 429 and attempt < 2:
                    wait = int(r.headers.get("Retry-After", "65"))
                    await asyncio.sleep(max(wait, 65))
                    continue
                r.raise_for_status()
                return r.json()
        return {}

    # ── Raw JSON (para caché) ─────────────────────────────────────────────

    async def get_fixtures_raw(self) -> dict:
        return await self._get(f"{BASE_URL}/competitions/{COMPETITION_ID}/matches")

    async def get_standings_raw(self) -> dict:
        return await self._get(f"{BASE_URL}/competitions/{COMPETITION_ID}/standings")

    # ── Parse desde JSON (reutilizable con caché) ─────────────────────────

    def parse_fixtures(self, raw: dict) -> list[Match]:
        return [self._parse_match(m) for m in raw.get("matches", [])]

    def parse_standings(self, raw: dict) -> list[TeamStanding]:
        standings: list[TeamStanding] = []
        for group_data in raw.get("standings", []):
            if group_data.get("type") != "TOTAL":
                continue
            group_name = (group_data.get("group") or "").replace("_", " ").title()
            for entry in group_data["table"]:
                standings.append(self._parse_standing(entry, group_name))
        return standings

    # ── Métodos de alto nivel ─────────────────────────────────────────────

    async def get_fixtures(self) -> list[Match]:
        return self.parse_fixtures(await self.get_fixtures_raw())

    async def get_live_fixtures(self) -> list[Match]:
        # El filtro status= devuelve siempre vacío para esta competición
        # (bug del API) → consultar por fecha y filtrar del lado del cliente.
        now = datetime.now(timezone.utc)
        raw = await self._get(
            f"{BASE_URL}/competitions/{COMPETITION_ID}/matches",
            params={
                "dateFrom": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
                "dateTo": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
            },
        )
        matches = [self._parse_match(m) for m in raw.get("matches", [])]
        return [m for m in matches if m.is_live]

    async def get_match(self, fixture_id: int) -> Match | None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(3):
                r = await client.get(
                    f"{BASE_URL}/matches/{fixture_id}",
                    headers=self._headers,
                )
                if r.status_code == 404:
                    return None
                if r.status_code == 429 and attempt < 2:
                    wait = int(r.headers.get("Retry-After", "65"))
                    await asyncio.sleep(max(wait, 65))
                    continue
                r.raise_for_status()
                return self._parse_match(r.json())
        return None

    async def get_standings(self) -> list[TeamStanding]:
        return self.parse_standings(await self.get_standings_raw())

    # ── Parsers ────────────────────────────────────────────────────────────

    def _parse_match(self, data: dict) -> Match:
        home_data = data["homeTeam"]
        away_data = data["awayTeam"]
        score_data = data["score"]
        full_time = score_data.get("fullTime") or {}

        try:
            match_date = datetime.fromisoformat(data["utcDate"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            match_date = datetime.now()

        status = _STATUS_MAP.get(data.get("status", "SCHEDULED"), MatchStatus.SCHEDULED)

        group = data.get("group") or data.get("stage") or ""
        group = group.replace("_", " ").title()

        events: list[MatchEvent] = []
        for goal in data.get("goals", []):
            events.append(MatchEvent(
                time=goal.get("minute") or 0,
                team_id=(goal.get("team") or {}).get("id", 0),
                player=(goal.get("scorer") or {}).get("name") or "",
                type="Goal",
                detail=(goal.get("type") or "Normal Goal").replace("_", " ").title(),
            ))
        for booking in data.get("bookings", []):
            events.append(MatchEvent(
                time=booking.get("minute") or 0,
                team_id=(booking.get("team") or {}).get("id", 0),
                player=(booking.get("player") or {}).get("name") or "",
                type="Card",
                detail=(booking.get("card") or "YELLOW").replace("_", " ").title(),
            ))

        match_id = data["id"]
        bracket = _WC2026_BRACKET.get(match_id)

        def _team_name(t: dict, bracket_slot: str | None) -> str:
            if t.get("id"):
                return t.get("shortName") or t.get("name") or "TBD"
            # Equipo TBD: usar bracket hardcodeado, luego lo que devuelva el API
            return (
                bracket_slot
                or t.get("name")
                or t.get("shortName")
                or "TBD"
            )

        venue = (data.get("venue") or "").strip() or _WC2026_VENUES.get(match_id, "")
        if not venue:
            for h in filter(None, [home_data.get("shortName"), home_data.get("name")]):
                for a in filter(None, [away_data.get("shortName"), away_data.get("name")]):
                    venue = _WC2026_PAIR_VENUES.get(frozenset({h, a}), "")
                    if venue:
                        break
                if venue:
                    break

        return Match(
            id=match_id,
            home=Team(
                id=home_data.get("id") or 0,
                name=_team_name(home_data, bracket[0] if bracket else None),
                logo=home_data.get("crest") or "",
            ),
            away=Team(
                id=away_data.get("id") or 0,
                name=_team_name(away_data, bracket[1] if bracket else None),
                logo=away_data.get("crest") or "",
            ),
            date=match_date,
            status=status,
            score=Score(home=full_time.get("home"), away=full_time.get("away")),
            elapsed=data.get("minute"),
            group=group,
            events=events,
            venue=venue,
        )

    def _parse_standing(self, entry: dict, group_name: str) -> TeamStanding:
        team = entry["team"]
        return TeamStanding(
            rank=entry["position"],
            team_id=team["id"],
            team_name=team.get("shortName") or team["name"],
            team_logo=team.get("crest", ""),
            group=group_name,
            played=entry["playedGames"],
            won=entry["won"],
            drawn=entry["draw"],
            lost=entry["lost"],
            goals_for=entry["goalsFor"],
            goals_against=entry["goalsAgainst"],
            goal_difference=entry["goalDifference"],
            points=entry["points"],
        )
