import flet as ft
from src.services.live_service import LiveService
from src.models.match import Match
from src.ui.theme import COLORS
from src.ui.components.match_card import build_match_card
from src.ui.components.match_modal import open_match_modal
from src.ui.components.nav_bar import build_nav_bar
from src.ui.components.app_drawer import build_hamburger, build_refresh_btn
from src.ui.translations import round_name, round_order, is_knockout


class FixturesScreen:
    def __init__(self, page: ft.Page, live_service: LiveService) -> None:
        self._page = page
        self._service = live_service
        self._body = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

    def build(self) -> ft.View:
        self._service.on_update(self._on_update)
        self._render()

        return ft.View(
            route="/fixtures",
            controls=[
                ft.Column([
                    ft.Container(
                        content=ft.Row([
                            build_hamburger(self._page),
                            ft.Text(
                                "Fixture Completo",
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
            navigation_bar=build_nav_bar(self._page, 1),
            bgcolor=COLORS["bg"],
            padding=0,
        )

    def _render(self) -> None:
        self._body.controls.clear()
        matches = self._service.matches

        group_matches = [m for m in matches if not is_knockout(m.group)]
        knockout_matches = [m for m in matches if is_knockout(m.group)]

        # ── Fase de grupos: agrupadas por fecha ────────────────────────────
        if group_matches:
            self._body.controls.append(_round_header("Fase de Grupos"))
            by_date: dict[str, list[Match]] = {}
            for m in group_matches:
                key = _date_label(m)
                by_date.setdefault(key, []).append(m)

            for date_label, day_matches in by_date.items():
                self._body.controls.append(_date_subheader(date_label))
                for m in day_matches:
                    self._body.controls.append(
                        build_match_card(m, on_tap=lambda _, match=m: open_match_modal(self._page, match))
                    )

        # ── Fases eliminatorias: agrupadas por ronda ───────────────────────
        if knockout_matches:
            by_round: dict[str, list[Match]] = {}
            for m in knockout_matches:
                rnd = round_name(m.group)
                by_round.setdefault(rnd, []).append(m)

            for rnd in sorted(by_round, key=round_order):
                self._body.controls.append(_round_header(rnd))
                for idx, m in enumerate(sorted(by_round[rnd], key=lambda x: x.date), start=1):
                    self._body.controls.append(
                        build_match_card(m, on_tap=lambda _, match=m: open_match_modal(self._page, match))
                    )

        if not matches:
            err = self._service.load_error
            lines: list[ft.Control] = [
                ft.Text("Sin partidos disponibles", color=COLORS["text_secondary"], size=14),
            ]
            if err:
                lines += [
                    ft.Text(err, color=COLORS["red"], size=10, selectable=True,
                           text_align=ft.TextAlign.CENTER),
                    ft.Text("Tocá 🔄 para reintentar", color=COLORS["text_secondary"],
                           size=11, italic=True),
                ]
            self._body.controls.append(
                ft.Container(
                    content=ft.Column(
                        lines,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    padding=ft.padding.all(40),
                    alignment=ft.alignment.center,
                )
            )

    def _on_update(self) -> None:
        self._render()
        self._page.update()


# ── Helpers de UI ──────────────────────────────────────────────────────────────

def _round_header(label: str) -> ft.Container:
    return ft.Container(
        content=ft.Row([
            ft.Container(width=3, height=18, bgcolor=COLORS["primary"], border_radius=2),
            ft.Text(label, size=14, weight=ft.FontWeight.BOLD, color=COLORS["primary"]),
        ], spacing=10),
        padding=ft.padding.only(left=16, top=22, right=20, bottom=8),
    )


def _date_subheader(label: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(label, size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_secondary"]),
        padding=ft.padding.only(left=20, top=12, right=20, bottom=4),
    )


def _date_label(m: Match) -> str:
    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    d = m.date.astimezone()
    return f"{days[d.weekday()]} {d.day} {months[d.month - 1]}"
