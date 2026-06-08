import re

_TEAMS_ES: dict[str, str] = {
    # Europa
    "Germany": "Alemania", "France": "Francia", "England": "Inglaterra",
    "Netherlands": "Países Bajos", "Holland": "Países Bajos",
    "Belgium": "Bélgica", "Portugal": "Portugal", "Spain": "España",
    "Switzerland": "Suiza", "Denmark": "Dinamarca", "Croatia": "Croacia",
    "Serbia": "Serbia", "Austria": "Austria", "Turkey": "Turquía",
    "Türkiye": "Turquía", "Scotland": "Escocia", "Wales": "Gales",
    "Ukraine": "Ucrania", "Hungary": "Hungría", "Slovakia": "Eslovaquia",
    "Czech Republic": "Rep. Checa", "Czechia": "Rep. Checa",
    "Romania": "Rumanía", "Poland": "Polonia", "Norway": "Noruega",
    "Sweden": "Suecia", "Greece": "Grecia", "Albania": "Albania",
    "Georgia": "Georgia", "Finland": "Finlandia", "Slovenia": "Eslovenia",
    "North Macedonia": "Macedonia del Norte", "Luxembourg": "Luxemburgo",
    "Iceland": "Islandia", "Ireland": "Irlanda",
    "Bosnia and Herzegovina": "Bosnia y Herzegovina",
    "Kosovo": "Kosovo", "Montenegro": "Montenegro",
    "Bulgaria": "Bulgaria", "Belarus": "Bielorrusia", "Italy": "Italia",
    "Russia": "Rusia", "Israel": "Israel",
    # América
    "Brazil": "Brasil", "Argentina": "Argentina", "Uruguay": "Uruguay",
    "Colombia": "Colombia", "Ecuador": "Ecuador", "Paraguay": "Paraguay",
    "Venezuela": "Venezuela", "Chile": "Chile", "Peru": "Perú",
    "Bolivia": "Bolivia", "United States": "Estados Unidos", "USA": "EE. UU.",
    "Mexico": "México", "Canada": "Canadá", "Panama": "Panamá",
    "Costa Rica": "Costa Rica", "Honduras": "Honduras",
    "El Salvador": "El Salvador", "Jamaica": "Jamaica",
    "Trinidad and Tobago": "Trinidad y Tobago",
    "Cuba": "Cuba", "Curaçao": "Curazao", "Curacao": "Curazao",
    "Guatemala": "Guatemala", "Haiti": "Haití",
    # Asia / Oceanía
    "Japan": "Japón", "South Korea": "Corea del Sur",
    "Korea Republic": "Corea del Sur", "Korea DPR": "Corea del Norte",
    "North Korea": "Corea del Norte", "Australia": "Australia",
    "Iran": "Irán", "Iraq": "Irak", "Jordan": "Jordania",
    "Qatar": "Catar", "Uzbekistan": "Uzbekistán",
    "UAE": "Emiratos Árabes", "United Arab Emirates": "Emiratos Árabes",
    "Saudi Arabia": "Arabia Saudita", "Oman": "Omán",
    "Bahrain": "Baréin", "China PR": "China", "China": "China",
    "Kuwait": "Kuwait", "Indonesia": "Indonesia",
    "Kyrgyzstan": "Kirguistán", "Thailand": "Tailandia",
    "Palestine": "Palestina", "Tajikistan": "Tayikistán",
    "Vietnam": "Vietnam", "India": "India", "Malaysia": "Malasia",
    "Philippines": "Filipinas", "New Zealand": "Nueva Zelanda",
    # África
    "Morocco": "Marruecos", "Senegal": "Senegal", "Nigeria": "Nigeria",
    "Egypt": "Egipto", "Ivory Coast": "Costa de Marfil",
    "Côte d'Ivoire": "Costa de Marfil", "Cote d'Ivoire": "Costa de Marfil",
    "Ghana": "Ghana", "Algeria": "Argelia", "Tunisia": "Túnez",
    "Cameroon": "Camerún", "South Africa": "Sudáfrica",
    "DR Congo": "Rep. Dem. del Congo", "Congo DR": "Rep. Dem. del Congo",
    "Tanzania": "Tanzania", "Guinea": "Guinea", "Mali": "Malí",
    "Zambia": "Zambia", "Mozambique": "Mozambique",
    "Benin": "Benín", "Comoros": "Comoras", "Uganda": "Uganda",
    "Angola": "Angola", "Zimbabwe": "Zimbabue", "Kenya": "Kenia",
    "Ethiopia": "Etiopía", "Sudan": "Sudán",
    "Burkina Faso": "Burkina Faso", "Gabon": "Gabón",
    "Rwanda": "Ruanda", "Togo": "Togo",
    "Namibia": "Namibia", "Cape Verde": "Cabo Verde",
    "Libya": "Libia", "Niger": "Níger",
}

_ROUNDS_ES: dict[str, str] = {
    "GROUP_STAGE": "Fase de Grupos",
    "LAST_32": "Dieciseisavos de Final",
    "ROUND_OF_32": "Dieciseisavos de Final",
    "LAST_16": "Octavos de Final",
    "ROUND_OF_16": "Octavos de Final",
    "QUARTER_FINALS": "Cuartos de Final",
    "SEMI_FINALS": "Semifinales",
    "THIRD_PLACE": "Tercer y Cuarto Puesto",
    "PLAY_OFF_FOR_THIRD_PLACE": "Tercer y Cuarto Puesto",
    "FINAL": "Final",
    # Versiones title-case (ya procesadas en el parser)
    "Group Stage": "Fase de Grupos",
    "Last 32": "Dieciseisavos de Final",
    "Last 16": "Octavos de Final",
    "Quarter Finals": "Cuartos de Final",
    "Semi Finals": "Semifinales",
    "Third Place": "Tercer y Cuarto Puesto",
    "Play Off For Third Place": "Tercer y Cuarto Puesto",
    "Final": "Final",
}

_ROUND_ORDER = [
    "Fase de Grupos",
    "Dieciseisavos de Final",
    "Octavos de Final",
    "Cuartos de Final",
    "Semifinales",
    "Tercer y Cuarto Puesto",
    "Final",
]

# Patrones de API para equipos TBD en fases eliminatorias
# NOTA: se busca en texto en minúsculas → usar [a-l], luego .upper() en la salida
_BRACKET_PATTERNS = [
    (r"winner\s+group\s+([a-l])", lambda m: f"1° Grupo {m.group(1).upper()}"),
    (r"runner[- ]up\s+group\s+([a-l])", lambda m: f"2° Grupo {m.group(1).upper()}"),
    (r"1st\s+group\s+([a-l])", lambda m: f"1° Grupo {m.group(1).upper()}"),
    (r"2nd\s+group\s+([a-l])", lambda m: f"2° Grupo {m.group(1).upper()}"),
    (r"3rd\s+(?:place\s+)?group\s+([a-l])", lambda m: f"3° Grupo {m.group(1).upper()}"),
    (r"winner\s+match\s+(\d+)", lambda m: f"Ganador Partido {m.group(1)}"),
    (r"best\s+third[- ]placed?\s+(.+)", lambda m: f"Mejor 3° ({m.group(1).upper()})"),
    (r"(\d+)(?:st|nd|rd|th)\s+group\s+([a-l])", lambda m: f"{m.group(1)}° Grupo {m.group(2).upper()}"),
]


def team_name(name: str) -> str:
    if not name:
        return "Por definir"
    # Intentar traducción directa
    translated = _TEAMS_ES.get(name)
    if translated:
        return translated
    # Intentar interpretar como descripción de bracket ("Winner Group A", etc.)
    bracket = bracket_placeholder(name)
    if bracket != name:
        return bracket
    # Si era literalmente "TBD" sin info adicional
    if name.upper() == "TBD":
        return "Por definir"
    return name


def round_name(stage: str) -> str:
    return _ROUNDS_ES.get(stage, stage)


def round_order(stage_es: str) -> int:
    try:
        return _ROUND_ORDER.index(stage_es)
    except ValueError:
        return -1


def bracket_placeholder(text: str) -> str:
    if not text or text == "TBD":
        return "Por definir"
    t_lower = text.strip().lower()
    for pattern, formatter in _BRACKET_PATTERNS:
        m = re.search(pattern, t_lower)
        if m:
            return formatter(m)
    return text


def is_knockout(group: str) -> bool:
    return not group.lower().startswith("group")
