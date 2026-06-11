import os
import asyncio
from dotenv import load_dotenv
from src.models.match import Match

load_dotenv()

# gemini-1.5-flash fue retirado por Google (404); 2.0-flash no tiene cuota
# en el plan gratuito. 2.5-flash funciona con la clave del proyecto.
_MODEL = "gemini-2.5-flash"

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client


def _generate_sync(prompt: str) -> str:
    """Corre en un thread: el import de google.genai tarda varios segundos
    en Android y congelaba la UI si se hacía en el event loop."""
    from google.genai import types
    response = _get_client().models.generate_content(
        model=_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=800,
            # Sin presupuesto de razonamiento: respuesta directa y rápida
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return (response.text or "").strip() or "Sin análisis disponible."


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

    return await asyncio.to_thread(_generate_sync, prompt)
