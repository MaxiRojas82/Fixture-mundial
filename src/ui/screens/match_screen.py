import asyncio
import flet as ft
from src.services.live_service import LiveService
from src.models.match import Match, MatchStatus
from src.api.ai_client import analyze_match
from src.ui.theme import COLORS
from src.ui.flags import get_flag_url, get_flag_b64
from src.ui.translations import team_name
from src.ui.components.nav_bar import build_nav_bar


class MatchScreen:
    def __init__(self, page: ft.Page, live_service: LiveService, match_id: int) -> None:
        self._page = page
        self._service = live_service
        self._match_id = match_id
        self._match: Match | None = None

        # Widgets actualizables
        self._score_text = ft.Text("vs", size=46, weight=ft.FontWeight.BOLD, color=COLORS["primary"])
        self._home_flag = ft.Image(width=56, height=38, fit=ft.ImageFit.CONTAIN, border_radius=4)
        self._away_flag = ft.Image(width=56, height=38, fit=ft.ImageFit.CONTAIN, border_radius=4)
        self._home_name = ft.Text("---", size=15, color=COLORS["text"], weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER, no_wrap=False)
        self._away_name = ft.Text("---", size=15, color=COLORS["text"], weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER, no_wrap=False)
        self._status_text = ft.Text("", size=13, color=COLORS["text_secondary"])
        self._venue_text = ft.Text("", size=11, color=COLORS["text_secondary"], text_align=ft.TextAlign.CENTER, no_wrap=False)
        self._events_col = ft.Column(spacing=6)
        self._ai_text = ft.Text(
            "Cargando análisis IA...",
            size=13,
            color=COLORS["text_secondary"],
            italic=True,
        )

    def build(self) -> ft.View:
        view = ft.View(
            route=f"/match/{self._match_id}",
            controls=[
                ft.Column([
                    self._build_top_bar(),
                    ft.Column([
                        ft.Container(height=12),
                        self._build_scoreboard(),
                        ft.Container(height=10),
                        self._build_events_card(),
                        ft.Container(height=10),
                        self._build_ai_card(),
                        ft.Container(height=28),
                    ], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0),
                ], expand=True, spacing=0),
            ],
            navigation_bar=build_nav_bar(self._page, -1),
            bgcolor=COLORS["bg"],
            padding=0,
        )
        asyncio.create_task(self._load())
        return view

    # ── Construcción de secciones ──────────────────────────────────────────

    def _go_back(self) -> None:
        if len(self._page.views) > 1:
            self._page.views.pop()
            self._page.update()
        else:
            self._page.go("/")

    def _build_top_bar(self) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.IconButton(
                    ft.Icons.ARROW_BACK_IOS_NEW,
                    icon_color=COLORS["text"],
                    icon_size=20,
                    on_click=lambda _: self._go_back(),
                ),
                ft.Text(
                    "Detalle del partido",
                    size=17,
                    weight=ft.FontWeight.BOLD,
                    color=COLORS["text"],
                    expand=True,
                ),
            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=8, top=48, right=8, bottom=10),
            bgcolor=COLORS["surface"],
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=COLORS["shadow"],
                offset=ft.Offset(0, 2),
            ),
        )

    def _build_scoreboard(self) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column([
                        self._home_flag,
                        self._home_name,
                    ], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    ft.Column([
                        self._score_text,
                        self._status_text,
                        ft.Row([
                            ft.Icon(ft.Icons.LOCATION_ON_OUTLINED, size=12, color=COLORS["text_secondary"]),
                            self._venue_text,
                        ], spacing=3, alignment=ft.MainAxisAlignment.CENTER,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    ft.Column([
                        self._away_flag,
                        self._away_name,
                    ], expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]),
            padding=ft.padding.symmetric(horizontal=20, vertical=24),
            margin=ft.margin.symmetric(horizontal=16),
            bgcolor=COLORS["card"],
            border_radius=18,
        )

    def _build_events_card(self) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text("EVENTOS", size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_secondary"]),
                self._events_col,
            ], spacing=12),
            padding=ft.padding.all(16),
            margin=ft.margin.symmetric(horizontal=16),
            bgcolor=COLORS["card"],
            border_radius=18,
        )

    def _build_ai_card(self) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("✨", size=16),
                    ft.Text("Análisis IA", size=13, weight=ft.FontWeight.BOLD, color=COLORS["primary"]),
                ], spacing=8),
                self._ai_text,
            ], spacing=10),
            padding=ft.padding.all(16),
            margin=ft.margin.symmetric(horizontal=16),
            bgcolor=COLORS["card"],
            border_radius=18,
        )

    # ── Carga y actualización ──────────────────────────────────────────────

    async def _load(self) -> None:
        self._match = await self._service.get_match(self._match_id)
        if not self._match:
            return
        self._refresh_ui()
        asyncio.create_task(self._load_ai())
        if self._match.is_live:
            self._service.on_update(self._on_update)

    async def _load_ai(self) -> None:
        if not self._match:
            return
        try:
            text = await analyze_match(self._match)
            self._ai_text.value = text
            self._ai_text.italic = False
            self._ai_text.color = COLORS["text"]
        except Exception:
            self._ai_text.value = "No se pudo cargar el análisis IA."
        self._page.update()

    def _refresh_ui(self) -> None:
        if not self._match:
            return
        m = self._match

        self._home_name.value = team_name(m.home.name)
        self._away_name.value = team_name(m.away.name)
        def _set_flag(img: ft.Image, name: str) -> None:
            b64 = get_flag_b64(name)
            if b64:
                img.src_base64 = b64
                img.src = None
                img.visible = True
            else:
                url = get_flag_url(name, 80)
                if url:
                    img.src = url
                    img.src_base64 = None
                    img.visible = True
                else:
                    img.visible = False
        _set_flag(self._home_flag, m.home.name)
        _set_flag(self._away_flag, m.away.name)
        self._score_text.value = "vs" if m.score.home is None and m.score.away is None else m.score_display
        self._venue_text.value = m.venue

        if m.is_live:
            mins = m.display_minute
            self._status_text.value = f"🔴  EN VIVO  ·  ~{mins}'" if mins else "🔴  EN VIVO"
            self._status_text.color = COLORS["live"]
            self._score_text.color = COLORS["live"]
        elif m.status == MatchStatus.HALFTIME:
            self._status_text.value = "⏸  Medio tiempo"
            self._status_text.color = COLORS["yellow"]
            self._score_text.color = COLORS["yellow"]
        elif m.status == MatchStatus.FINISHED:
            self._status_text.value = "Partido finalizado"
            self._status_text.color = COLORS["text_secondary"]
            self._score_text.color = COLORS["text"]
        else:
            self._status_text.value = m.date.astimezone().strftime("%d %b %Y  ·  %H:%M")
            self._status_text.color = COLORS["text_secondary"]
            self._score_text.color = COLORS["text_secondary"]

        # Eventos: goles y tarjetas, ordenados por minuto
        _DETALLE = {
            "Normal Goal": "Gol",
            "Penalty":     "Penal",
            "Own Goal":    "En contra",
            "Yellow Card": "Amarilla",
            "Red Card":    "Roja",
        }
        self._events_col.controls.clear()
        events = sorted(
            [e for e in m.events if e.type in ("Goal", "Card")],
            key=lambda e: e.time,
        )
        if not events:
            self._events_col.controls.append(
                ft.Text("Sin eventos registrados", size=13, color=COLORS["text_secondary"])
            )
        for ev in events:
            raw_name = m.home.name if ev.team_id == m.home.id else m.away.name
            if ev.type == "Goal":
                icon = "⚽"
            elif "red" in ev.detail.lower():
                icon = "🟥"
            else:
                icon = "🟨"
            detalle = _DETALLE.get(ev.detail, ev.detail)
            self._events_col.controls.append(
                ft.Row([
                    ft.Text(f"{ev.time}'", size=12, color=COLORS["text_secondary"], width=34),
                    ft.Text(icon, size=14),
                    ft.Column([
                        ft.Text(ev.player or "—", size=13, color=COLORS["text"]),
                        ft.Text(f"{team_name(raw_name)}  ·  {detalle}", size=11, color=COLORS["text_secondary"]),
                    ], spacing=1, expand=True),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            )

        self._page.update()

    def _on_update(self) -> None:
        updated = next((m for m in self._service.matches if m.id == self._match_id), None)
        if updated:
            self._match = updated
            self._refresh_ui()
