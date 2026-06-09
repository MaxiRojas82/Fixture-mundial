import flet as ft
from src.services.live_service import LiveService
from src.models.match import Match
from src.ui.theme import COLORS
from src.ui.components.nav_bar import build_nav_bar
from src.ui.components.app_drawer import build_hamburger, build_refresh_btn
from src.ui.components.match_card import build_match_card
from src.ui.translations import round_name, round_order, is_knockout


_ROUND_META: dict[str, tuple[str, str]] = {
    "Dieciseisavos de Final": ("⚽", "#FF8C42"),
    "Octavos de Final":       ("🥊", "#FFC300"),
    "Cuartos de Final":       ("⚡", "#00D2FF"),
    "Semifinales":            ("🔥", "#9B5DE5"),
    "Tercer y Cuarto Puesto": ("🥉", "#A0AEC0"),
    "Final":                  ("🏆", "#FFD700"),
}


class BracketScreen:
    def __init__(self, page: ft.Page, live_service: LiveService) -> None:
        self._page = page
        self._service = live_service
        self._body = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

    def build(self) -> ft.View:
        self._service.on_update(self._on_update)
        self._render()
        return ft.View(
            route="/bracket",
            controls=[
                ft.Column([
                    self._build_header(),
                    self._body,
                ], expand=True, spacing=0),
            ],
            navigation_bar=build_nav_bar(self._page, 3),
            bgcolor=COLORS["bg"],
            padding=0,
        )

    def _build_header(self) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                build_hamburger(self._page),
                ft.Container(
                    content=ft.Text("🔱", size=22),
                    bgcolor=COLORS["primary"] + "22",
                    border_radius=10,
                    padding=ft.padding.all(8),
                ),
                ft.Text(
                    "Llaves",
                    size=22,
                    weight=ft.FontWeight.BOLD,
                    color=COLORS["text"],
                    expand=True,
                ),
                build_refresh_btn(self._page, self._service),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=8, top=52, right=8, bottom=16),
            bgcolor=COLORS["surface"],
            shadow=ft.BoxShadow(blur_radius=8, color=COLORS["shadow"], offset=ft.Offset(0, 2)),
        )

    def _render(self) -> None:
        self._body.controls.clear()
        knockout = [m for m in self._service.matches if is_knockout(m.group)]

        if not knockout:
            self._body.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text("🔱", size=52, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            "Las llaves estarán disponibles\ncuando arranque la fase eliminatoria",
                            color=COLORS["text_secondary"],
                            text_align=ft.TextAlign.CENTER,
                            size=14,
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    padding=ft.padding.symmetric(vertical=60),
                    alignment=ft.alignment.center,
                )
            )
            return

        by_round: dict[str, list[Match]] = {}
        for m in knockout:
            rnd = round_name(m.group)
            by_round.setdefault(rnd, []).append(m)

        for rnd in sorted(by_round, key=round_order):
            icon, color = _ROUND_META.get(rnd, ("⚽", COLORS["primary"]))
            self._body.controls.append(_round_banner(rnd, icon, color))
            for m in sorted(by_round[rnd], key=lambda x: x.date):
                self._body.controls.append(
                    build_match_card(m, on_tap=lambda _, mid=m.id: self._page.go(f"/match/{mid}"), show_date=True)
                )

        self._body.controls.append(ft.Container(height=16))

    def _on_update(self) -> None:
        self._render()
        self._page.update()


def _round_banner(label: str, icon: str, color: str) -> ft.Container:
    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Text(icon, size=16),
                bgcolor=color + "22",
                border_radius=10,
                padding=ft.padding.all(7),
                width=36,
                height=36,
                alignment=ft.alignment.center,
            ),
            ft.Text(label.upper(), size=12, weight=ft.FontWeight.BOLD, color=color),
        ], spacing=10),
        padding=ft.padding.only(left=16, top=20, right=20, bottom=8),
    )
