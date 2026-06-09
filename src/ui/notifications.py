_notifications_on: bool = True
_favorites: set[str] = set()


def get_favorites() -> set[str]:
    return _favorites.copy()


def toggle_favorite(team: str) -> None:
    if team in _favorites:
        _favorites.discard(team)
    else:
        _favorites.add(team)


def is_favorite(team: str) -> bool:
    return team in _favorites


def should_notify_match(home: str, away: str) -> bool:
    """Sin favoritos → notifica todo. Con favoritos → solo si el equipo es favorito."""
    if not _favorites:
        return True
    return home in _favorites or away in _favorites


_settings: dict[str, bool] = {
    "goal":        True,
    "penalty":     True,
    "kickoff":     True,
    "halftime":    True,
    "fulltime":    True,
    "yellow_card": False,
    "red_card":    True,
}

# (key, emoji, label, accent_hex)
EVENTS: list[tuple[str, str, str, str]] = [
    ("goal",        "⚽", "Gol",                "#FF1744"),
    ("penalty",     "🎯", "Tiro penal",          "#FFD600"),
    ("kickoff",     "▶️",  "Inicio del partido",  "#00E676"),
    ("halftime",    "⏸",  "Medio tiempo",         "#FFD600"),
    ("fulltime",    "🏁", "Final del partido",    "#8892A4"),
    ("yellow_card", "🟨", "Tarjeta amarilla",     "#FFD600"),
    ("red_card",    "🟥", "Tarjeta roja",         "#FF1744"),
]


def notifications_enabled() -> bool:
    return _notifications_on


def toggle_notifications() -> bool:
    global _notifications_on
    _notifications_on = not _notifications_on
    return _notifications_on


def is_enabled(event_type: str) -> bool:
    return _notifications_on and _settings.get(event_type, True)


def set_enabled(event_type: str, value: bool) -> None:
    _settings[event_type] = value


def event_accent(event_type: str) -> str:
    for key, _, _, color in EVENTS:
        if key == event_type:
            return color
    return "#00D2FF"


def event_icon(event_type: str) -> str:
    for key, icon, _, _ in EVENTS:
        if key == event_type:
            return icon
    return "🔔"
