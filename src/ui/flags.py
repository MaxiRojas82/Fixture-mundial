_CODES: dict[str, str] = {
    # CONMEBOL
    "Argentina": "ar", "Brazil": "br", "Brasil": "br",
    "Uruguay": "uy", "Colombia": "co", "Ecuador": "ec",
    "Paraguay": "py", "Venezuela": "ve", "Chile": "cl",
    "Peru": "pe", "Perú": "pe", "Bolivia": "bo",

    # CONCACAF
    "United States": "us", "USA": "us", "US": "us",
    "Canada": "ca", "Mexico": "mx", "México": "mx",
    "Panama": "pa", "Panamá": "pa", "Costa Rica": "cr",
    "Honduras": "hn", "El Salvador": "sv",
    "Jamaica": "jm", "Trinidad and Tobago": "tt", "Trinidad": "tt",
    "Cuba": "cu", "Curaçao": "cw", "Curacao": "cw",
    "Guatemala": "gt", "Haiti": "ht",

    # UEFA
    "Germany": "de", "Deutschland": "de",
    "France": "fr", "Spain": "es", "España": "es",
    "Portugal": "pt", "England": "gb-eng",
    "Netherlands": "nl", "Holland": "nl",
    "Belgium": "be", "Austria": "at",
    "Turkey": "tr", "Türkiye": "tr",
    "Scotland": "gb-sct", "Wales": "gb-wls",
    "Ukraine": "ua", "Hungary": "hu",
    "Denmark": "dk", "Croatia": "hr", "Hrvatska": "hr",
    "Serbia": "rs", "Slovakia": "sk",
    "Czech Republic": "cz", "Czechia": "cz", "Romania": "ro",
    "Switzerland": "ch", "Sweden": "se",
    "Poland": "pl", "Norway": "no", "Greece": "gr",
    "Italy": "it", "Russia": "ru", "Albania": "al",
    "Georgia": "ge", "Finland": "fi", "Slovenia": "si",
    "North Macedonia": "mk", "Luxembourg": "lu",
    "Iceland": "is", "Ireland": "ie",
    "Bosnia and Herzegovina": "ba", "Bosnia": "ba",
    "Bosnia-Herzegovina": "ba", "Bosnia-H.": "ba",
    "Kosovo": "xk", "Montenegro": "me",
    "Bulgaria": "bg", "Belarus": "by",
    "Israel": "il", "Northern Ireland": "gb-nir",

    # AFC
    "Japan": "jp", "South Korea": "kr", "Korea Republic": "kr",
    "Korea DPR": "kp", "North Korea": "kp",
    "Australia": "au", "Iran": "ir",
    "Jordan": "jo", "Qatar": "qa",
    "Uzbekistan": "uz", "Iraq": "iq",
    "UAE": "ae", "United Arab Emirates": "ae",
    "Saudi Arabia": "sa", "Oman": "om",
    "Bahrain": "bh", "China": "cn", "China PR": "cn",
    "Kuwait": "kw", "Indonesia": "id", "Kyrgyzstan": "kg",
    "Thailand": "th", "Palestine": "ps",
    "Tajikistan": "tj", "Vietnam": "vn",
    "India": "in", "Hong Kong": "hk",
    "Malaysia": "my", "Singapore": "sg",
    "Philippines": "ph", "Myanmar": "mm",
    "Syria": "sy", "Lebanon": "lb",
    "Yemen": "ye", "Afghanistan": "af",
    "Nepal": "np", "Pakistan": "pk",
    "Bangladesh": "bd", "Mongolia": "mn",
    "Cambodia": "kh", "Laos": "la",

    # CAF
    "Morocco": "ma", "Maroc": "ma",
    "Senegal": "sn", "Nigeria": "ng",
    "Egypt": "eg", "Ivory Coast": "ci",
    "Côte d'Ivoire": "ci", "Cote d'Ivoire": "ci",
    "Ghana": "gh", "Algeria": "dz",
    "Tunisia": "tn", "Cameroon": "cm",
    "South Africa": "za", "DR Congo": "cd",
    "Congo DR": "cd", "Congo": "cg",
    "Tanzania": "tz", "Guinea": "gn", "Mali": "ml",
    "Zambia": "zm", "Mozambique": "mz",
    "Benin": "bj", "Comoros": "km",
    "Uganda": "ug", "Angola": "ao",
    "Zimbabwe": "zw", "Kenya": "ke",
    "Ethiopia": "et", "Sudan": "sd",
    "Burkina Faso": "bf", "Gabon": "ga",
    "Rwanda": "rw", "Togo": "tg",
    "Sierra Leone": "sl", "Gambia": "gm",
    "Namibia": "na", "Botswana": "bw",
    "Cape Verde": "cv", "Mauritania": "mr",
    "Libya": "ly", "Niger": "ne",
    "South Sudan": "ss", "Mali": "ml",

    # OFC
    "New Zealand": "nz", "Fiji": "fj",
    "Papua New Guinea": "pg",

    # Variantes adicionales del Mundial 2026
    "Cabo Verde": "cv",
    "Congo": "cd", "Congo DR": "cd", "DR Congo": "cd",
    "South Korea": "kr",
    "Korea Rep.": "kr", "Korea Rep": "kr",
    "Czech Rep.": "cz", "Czech Rep": "cz",
    "United Arab Emir.": "ae",
    "Burkina": "bf",
    "Ivory": "ci",
    "North Macedonia": "mk", "Macedonia": "mk",
}


import os as _os
import base64 as _base64

_FLAG_DIR = _os.path.join(_os.path.dirname(__file__), "..", "..", "assets", "flags")
_b64_cache: dict[str, str] = {}


def _get_code(team_name: str) -> str | None:
    code = _CODES.get(team_name)
    if not code:
        for key, c in _CODES.items():
            if key.lower() in team_name.lower() or team_name.lower() in key.lower():
                code = c
                break
    return code


def get_flag_url(team_name: str, size: int = 40) -> str | None:
    code = _get_code(team_name)
    if not code:
        return None
    return f"https://flagcdn.com/w{size}/{code}.png"


def get_flag_local(team_name: str) -> str | None:
    """Retorna la ruta al asset local (assets/flags/{code}.png) si existe."""
    code = _get_code(team_name)
    if not code:
        return None
    path = _os.path.normpath(_os.path.join(_FLAG_DIR, f"{code}.png"))
    if _os.path.exists(path):
        return f"flags/{code}.png"
    return None


def get_flag_b64(team_name: str) -> str | None:
    """Retorna base64 del flag local si existe (carga lazy desde disco)."""
    if team_name in _b64_cache:
        return _b64_cache[team_name]
    code = _get_code(team_name)
    if not code:
        return None
    path = _os.path.normpath(_os.path.join(_FLAG_DIR, f"{code}.png"))
    if not _os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            data = _base64.b64encode(f.read()).decode()
        _b64_cache[team_name] = data
        return data
    except Exception:
        return None


async def prefetch_flags(team_names: list[str]) -> None:  # noqa: ARG001
    """No-op: los flags ya están en disco como assets."""
