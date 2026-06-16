import flet as ft

from src.services.live_service import LiveService
from src.ui.components.nav_bar import build_nav_bar
from src.ui.theme import COLORS
from src.ui.translations import team_name


class StatsScreen:
    def __init__(self, page: ft.Page, live_service: LiveService) -> None:
        self._page = page
        self._service = live_service
        self._tab_idx = 0
        self._content = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

    def build(self) -> ft.View:
        tabs = ft.Tabs(
            selected_index=0,
            on_change=self._on_tab_change,
            animation_duration=200,
            tabs=[
                ft.Tab(text="Bota de Oro"),
                ft.Tab(text="Balón de Oro"),
            ],
            indicator_color=COLORS["primary"],
            label_color=COLORS["primary"],
            unselected_label_color=COLORS["text_secondary"],
            expand=False,
        )
        view = ft.View(
            route="/stats",
            controls=[
                ft.Column([
                    self._build_top_bar(),
                    ft.Container(
                        content=tabs,
                        bgcolor=COLORS["surface"],
                        padding=ft.padding.only(bottom=2),
                    ),
                    self._content,
                ], expand=True, spacing=0),
            ],
            navigation_bar=build_nav_bar(self._page, 5),
            bgcolor=COLORS["bg"],
            padding=0,
        )
        self._service.on_update(self._on_update)
        return view

    def _build_top_bar(self) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.Text(
                    "Estadísticas",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    color=COLORS["text"],
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=20, top=52, right=20, bottom=16),
            bgcolor=COLORS["surface"],
            shadow=ft.BoxShadow(
                blur_radius=6,
                color=COLORS["shadow"],
                offset=ft.Offset(0, 2),
            ),
        )

    def _on_tab_change(self, e: ft.ControlEvent) -> None:
        self._tab_idx = e.control.selected_index
        self._render()
        try:
            self._page.update()
        except Exception:
            pass

    def _on_update(self) -> None:
        self._render()
        try:
            self._page.update()
        except Exception:
            pass

    def _render(self) -> None:
        self._content.controls.clear()
        if self._tab_idx == 0:
            self._render_scorers()
        else:
            self._render_balon_de_oro()

    # ── Tab: Goleadores ────────────────────────────────────────────────────

    def _render_scorers(self) -> None:
        scorers = self._service.get_top_scorers()
        if not scorers:
            self._content.controls.append(
                ft.Container(
                    content=ft.Text(
                        "Sin datos de goles todavía.\n"
                        "Los goleadores aparecen una vez que haya partidos jugados.",
                        size=13,
                        color=COLORS["text_secondary"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.alignment.center,
                    padding=ft.padding.all(48),
                )
            )
            return

        rows: list[ft.Control] = [
            ft.Container(
                content=ft.Row([
                    ft.Text("#", size=11, color=COLORS["text_secondary"],
                            width=36, text_align=ft.TextAlign.CENTER),
                    ft.Text("Jugador", size=11, color=COLORS["text_secondary"], expand=True),
                    ft.Text("Selección", size=11, color=COLORS["text_secondary"], width=96),
                    ft.Text("⚽", size=14, width=36, text_align=ft.TextAlign.CENTER),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                bgcolor=COLORS["surface"],
            ),
        ]

        for i, s in enumerate(scorers):
            rank = i + 1
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, str(rank))
            pen_txt = ""
            rows.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(medal, size=13, width=36, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            s["player"],
                            size=14,
                            color=COLORS["text"],
                            weight=ft.FontWeight.W_500,
                            expand=True,
                            no_wrap=True,
                        ),
                        ft.Text(
                            team_name(s["team"]),
                            size=11,
                            color=COLORS["text_secondary"],
                            width=96,
                            no_wrap=True,
                        ),
                        ft.Text(
                            f"{s['goals']}{pen_txt}",
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            color=COLORS["primary"],
                            width=36,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(horizontal=16, vertical=11),
                    bgcolor=COLORS["card"] if i % 2 == 0 else COLORS["bg"],
                )
            )

        self._content.controls.append(ft.Column(rows, spacing=0))

    # ── Tab: Asistencias ──────────────────────────────────────────────────

    def _render_assists(self) -> None:
        assists = self._service.get_top_assists()
        if not assists:
            self._content.controls.append(
                ft.Container(
                    content=ft.Text(
                        "Sin datos de asistencias todavía.\n"
                        "Aparecen una vez que ESPN reporte asistidores en los partidos.",
                        size=13,
                        color=COLORS["text_secondary"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.alignment.center,
                    padding=ft.padding.all(48),
                )
            )
            return

        rows: list[ft.Control] = [
            ft.Container(
                content=ft.Row([
                    ft.Text("#", size=11, color=COLORS["text_secondary"],
                            width=36, text_align=ft.TextAlign.CENTER),
                    ft.Text("Jugador", size=11, color=COLORS["text_secondary"], expand=True),
                    ft.Text("Selección", size=11, color=COLORS["text_secondary"], width=96),
                    ft.Text("🎯", size=14, width=36, text_align=ft.TextAlign.CENTER),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                bgcolor=COLORS["surface"],
            ),
        ]

        for i, s in enumerate(assists):
            rank = i + 1
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, str(rank))
            rows.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(medal, size=13, width=36, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            s["player"],
                            size=14,
                            color=COLORS["text"],
                            weight=ft.FontWeight.W_500,
                            expand=True,
                            no_wrap=True,
                        ),
                        ft.Text(
                            team_name(s["team"]),
                            size=11,
                            color=COLORS["text_secondary"],
                            width=96,
                            no_wrap=True,
                        ),
                        ft.Text(
                            str(s["assists"]),
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            color=COLORS["primary"],
                            width=36,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(horizontal=16, vertical=11),
                    bgcolor=COLORS["card"] if i % 2 == 0 else COLORS["bg"],
                )
            )

        self._content.controls.append(ft.Column(rows, spacing=0))

    # ── Tab: Balón de Oro ─────────────────────────────────────────────────

    def _render_balon_de_oro(self) -> None:
        standings = self._service.get_figura_standings()
        if not standings:
            self._content.controls.append(
                ft.Container(
                    content=ft.Text(
                        "Sin datos todavía.\n"
                        "El Balón de Oro se calcula según las figuras de cada partido.",
                        size=13,
                        color=COLORS["text_secondary"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.alignment.center,
                    padding=ft.padding.all(48),
                )
            )
            return

        rows: list[ft.Control] = [
            ft.Container(
                content=ft.Row([
                    ft.Text("#", size=11, color=COLORS["text_secondary"],
                            width=36, text_align=ft.TextAlign.CENTER),
                    ft.Text("Jugador", size=11, color=COLORS["text_secondary"], expand=True),
                    ft.Text("Selección", size=11, color=COLORS["text_secondary"], width=96),
                    ft.Text("⭐", size=14, width=36, text_align=ft.TextAlign.CENTER),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                bgcolor=COLORS["surface"],
            ),
        ]

        for i, s in enumerate(standings):
            rank = i + 1
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, str(rank))
            rows.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(medal, size=13, width=36, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            s["player"],
                            size=14,
                            color=COLORS["text"],
                            weight=ft.FontWeight.W_500,
                            expand=True,
                            no_wrap=True,
                        ),
                        ft.Text(
                            team_name(s["team"]),
                            size=11,
                            color=COLORS["text_secondary"],
                            width=96,
                            no_wrap=True,
                        ),
                        ft.Text(
                            str(s["figuras"]),
                            size=15,
                            weight=ft.FontWeight.BOLD,
                            color=COLORS["yellow"],
                            width=36,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(horizontal=16, vertical=11),
                    bgcolor=COLORS["card"] if i % 2 == 0 else COLORS["bg"],
                )
            )

        self._content.controls.append(ft.Column(rows, spacing=0))

