import os
import asyncio
from dotenv import load_dotenv
from src.models.match import Match

load_dotenv()

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6LY3Bt_U68elS67T0UEOyjvBE24xmTL4kLSYEZ-a-n6JQ"))
    return _client


async def analyze_match(match: Match) -> str:
    goals_text = ""
    for ev in match.events:
        if ev.type == "Goal":
            team = match.home.name if ev.team_id == match.home.id else match.away.name
            goals_text += f"- Min {ev.time}': {ev.player} ({team}) — {ev.detail}\n"

    estado = "En curso" if match.is_live else match.status.name
    minuto = f"Minuto ~{match.display_minute}'" if match.display_minute else ""

    prompt = f"""Eres un comentarista deportivo apasionado del fútbol. Analiza este partido del Mundial 2026 en español:

**{match.home.name}  {match.score_display}  {match.away.name}**
Estado: {estado} {minuto}
Ronda: {match.group}

Goles registrados:
{goals_text or "Sin goles aún"}

Escribe un análisis breve (3 párrafos cortos) sobre:
1. El desarrollo del partido y desempeño de ambos equipos
2. Jugadores o momentos clave hasta ahora
3. Expectativa o predicción del resultado final

Sé conciso, apasionado y usa lenguaje de narración deportiva."""

    from google.genai import types
    response = await asyncio.to_thread(
        _get_client().models.generate_content,
        model="gemini-1.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=450),
    )
    return response.text
