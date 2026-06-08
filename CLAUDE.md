# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Tech Stack

- **UI Framework**: [Flet](https://flet.dev/) — Python puro que compila a APK/AAB para Play Store (Flutter bajo el capó, Material Design 3)
- **Football API**: [football-data.org](https://www.football-data.org/) — gratuita, cubre fixtures, standings y goles del Mundial (competition ID `2000`)
- **AI Analysis**: Google Gemini `gemini-1.5-flash` via `google-generativeai` SDK
- **HTTP Client**: `httpx` (async)
- **Python**: 3.10+ requerido (usa union types `X | Y`)

## Comandos de Desarrollo

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar en modo desarrollo (ventana de escritorio)
flet run main.py

# Ejecutar con hot reload
flet run --hot main.py

# Compilar APK para Android
flet build apk

# Compilar App Bundle para Play Store
flet build aab
```

## Configuración del Entorno

Copiar `.env.example` a `.env` y completar:
- `FOOTBALL_API_KEY` — clave gratuita de [football-data.org](https://www.football-data.org/client/register)
- `GEMINI_API_KEY` — clave gratuita de [aistudio.google.com](https://aistudio.google.com/app/apikey)
- `WORLD_CUP_COMPETITION_ID` — por defecto `2000` (FIFA World Cup en football-data.org)

## Arquitectura

```
main.py                        # Entry point Flet, routing, init de LiveService
src/
  api/
    football_client.py         # Cliente HTTP async para football-data.org
    ai_client.py               # Llamada a Claude para análisis de partido
  models/
    match.py                   # Dataclasses: Match, Team, Score, MatchEvent, MatchStatus
    standing.py                # Dataclass: TeamStanding
  services/
    live_service.py            # Loop de polling; fuente de verdad del estado; dispara callbacks
  ui/
    theme.py                   # Dict COLORS y factory ft.Theme (tema oscuro)
    screens/
      home_screen.py           # Partidos en vivo + próximos, con overlay de alerta de gol
      fixtures_screen.py       # Fixture completo agrupado por fecha
      standings_screen.py      # Tabla de posiciones por grupo
      match_screen.py          # Detalle de partido en vivo, timeline de eventos, análisis IA
    components/
      match_card.py            # Tarjeta de partido reutilizable con indicador LIVE
      goal_alert.py            # Notificación flotante de gol
      nav_bar.py               # Barra de navegación inferior
```

## Patrones Clave

**Estado**: `LiveService` es la única fuente de verdad. Las pantallas se registran con `on_update()` y `on_goal()`. Al cambiar datos, los callbacks llaman `page.update()`.

**Routing**: `page.on_route_change` maneja el stack de vistas. Rutas: `/`, `/fixtures`, `/standings`, `/match/{id}`.

**Polling**: `LiveService` carga todos los fixtures al iniciar, luego polling de partidos en vivo cada `POLL_INTERVAL_SECONDS`. La detección de goles compara conjuntos de eventos entre polls.

**IA**: `analyze_match()` en `ai_client.py` se llama una vez por carga de pantalla de partido, usando Gemini 1.5 Flash para velocidad. Llama a la API sync en un thread (`asyncio.to_thread`) para no bloquear el loop. No se cachea.
