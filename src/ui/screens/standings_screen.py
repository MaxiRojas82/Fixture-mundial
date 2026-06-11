import flet as ft
from src.services.live_service import LiveService
from src.models.standing import TeamStanding
from src.ui.theme import COLORS
from src.ui.components.nav_bar import build_nav_bar
from src.ui.components.app_drawer import build_hamburger, build_refresh_btn
from src.ui.flags import get_flag_url, get_flag_b64


def _flag(team_name: str) -> ft.Control:
    b64 = get_flag_b64(team_name)
    if b64:
        return ft.Image(src_base64=b64, width=22, height=15, fit=ft.ImageFit.CONTAIN, border_radius=2)
    url = get_flag_url(team_name, 40)
    if url:
        return ft.Image(src=url, width=22, height=15, fit=ft.ImageFit.CONTAIN, border_radius=2)
    return ft.Container(width=22, height=15)


class StandingsScreen:
    def __init__(self, page: ft.Page, live_service: LiveService) -> None:
        self._page = page
        self._service = live_service
        self._body = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

    def build(self) -> ft.View:
        self._service.on_update(self._on_update)
        self._render()

        return ft.View(
            route="/standings",
            controls=[
                ft.Column([
                    ft.Container(
                        content=ft.Row([
                            build_hamburger(self._page),
                            ft.Text(
                                "Tabla de Posiciones",
                                size=22,
                                weight=ft.FontWeight.BOLD,
                                color=COLORS["text"],
                                expand=True,
                            ),
                            build_refresh_btn(self._page, self._service),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.padding.only(left=8, top=52, right=8, bottom=16),
                        bgcolor=COLORS["surface"],
                        shadow=ft.BoxShadow(
                            blur_radius=8,
                            color=COLORS["shadow"],
                            offset=ft.Offset(0, 2),
                        ),
                    ),
                    self._body,
                ], expand=True, spacing=0),
            ],
            navigation_bar=build_nav_bar(self._page, 2),
            bgcolor=COLORS["bg"],
            padding=0,
        )

    def _render(self) -> None:
        self._body.controls.clear()
        standings = self._service.standings

        by_group: dict[str, list[TeamStanding]] = {}
        for s in standings:
            by_group.setdefault(s.group, []).append(s)

        for group_name, entries in sorted(by_group.items()):
            self._body.controls.append(
                ft.Container(
                    content=ft.Text(
                        group_name,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=COLORS["primary"],
                    ),
                    padding=ft.padding.only(left=20, top=18, right=20, bottom=8),
                )
            )
            self._body.controls.append(self._build_group_table(entries))

        if not standings:
            self._body.controls.append(
                ft.Container(
                    content=ft.Text("Tabla no disponible aún", color=COLORS["text_secondary"]),
                    padding=ft.padding.all(40),
                    alignment=ft.alignment.center,
                )
            )

    def _build_group_table(self, entries: list[TeamStanding]) -> ft.Container:
        W = {"team": None, "pj": 30, "g": 30, "e": 30, "p": 30, "dg": 36, "pts": 38}

        def header_text(label: str, width, color=COLORS["text_secondary"]) -> ft.Text:
            return ft.Text(label, size=10, color=color, width=width, text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.BOLD)

        header = ft.Container(
            content=ft.Row([
                ft.Text("Equipo", size=10, color=COLORS["text_secondary"], expand=True, weight=ft.FontWeight.BOLD),
                header_text("PJ", W["pj"]),
                header_text("PG", W["g"]),
                header_text("PE", W["e"]),
                header_text("PP", W["p"]),
                header_text("DG", W["dg"]),
                header_text("Pts", W["pts"], color=COLORS["primary"]),
            ], spacing=0),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
        )

        sorted_entries = sorted(entries, key=lambda s: (-s.points, -s.goal_difference, -s.goals_for))
        rows: list[ft.Control] = [header]

        for i, s in enumerate(sorted_entries):
            dg_color = COLORS["green"] if s.goal_difference > 0 else (COLORS["red"] if s.goal_difference < 0 else COLORS["text"])
            qualify_color = COLORS["primary"] + "22" if i < 2 else "transparent"

            row = ft.Container(
                content=ft.Row([
                    ft.Row([
                        ft.Text(str(s.rank), size=11, color=COLORS["text_secondary"], width=18),
                        _flag(s.team_name),
                        ft.Text(s.team_name, size=12, color=COLORS["text"]),
                    ], spacing=6, expand=True),
                    ft.Text(str(s.played), size=12, color=COLORS["text"], width=W["pj"], text_align=ft.TextAlign.CENTER),
                    ft.Text(str(s.won), size=12, color=COLORS["text"], width=W["g"], text_align=ft.TextAlign.CENTER),
                    ft.Text(str(s.drawn), size=12, color=COLORS["text"], width=W["e"], text_align=ft.TextAlign.CENTER),
                    ft.Text(str(s.lost), size=12, color=COLORS["text"], width=W["p"], text_align=ft.TextAlign.CENTER),
                    ft.Text(f"{s.goal_difference:+}", size=12, color=dg_color, width=W["dg"], text_align=ft.TextAlign.CENTER),
                    ft.Text(str(s.points), size=13, color=COLORS["primary"], weight=ft.FontWeight.BOLD, width=W["pts"], text_align=ft.TextAlign.CENTER),
                ], spacing=0),
                padding=ft.padding.symmetric(horizontal=12, vertical=9),
                bgcolor=qualify_color,
            )
            rows.append(row)

        return ft.Container(
            content=ft.Column(rows, spacing=0),
            bgcolor=COLORS["card"],
            border_radius=14,
            border=ft.border.all(1, COLORS["card_border"]),
            margin=ft.margin.symmetric(horizontal=16, vertical=4),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            shadow=ft.BoxShadow(
                blur_radius=10,
                spread_radius=0,
                color=COLORS["shadow"],
                offset=ft.Offset(0, 2),
            ),
        )

    def _on_update(self) -> None:
        self._render()
        self._page.update()
