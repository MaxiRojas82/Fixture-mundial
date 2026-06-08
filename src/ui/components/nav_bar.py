import flet as ft
from src.ui.theme import COLORS


def build_nav_bar(page: ft.Page, selected_index: int = 0) -> ft.NavigationBar:
    def on_change(e: ft.ControlEvent) -> None:
        routes = ["/", "/fixtures", "/standings", "/bracket", "/prode"]
        page.go(routes[e.control.selected_index])

    return ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME_OUTLINED,
                selected_icon=ft.Icons.HOME,
                label="Inicio",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.SPORTS_SOCCER_OUTLINED,
                selected_icon=ft.Icons.SPORTS_SOCCER,
                label="Fixture",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.TABLE_CHART_OUTLINED,
                selected_icon=ft.Icons.TABLE_CHART,
                label="Grupos",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.ACCOUNT_TREE_OUTLINED,
                selected_icon=ft.Icons.ACCOUNT_TREE,
                label="Llaves",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.STAR_BORDER_ROUNDED,
                selected_icon=ft.Icons.STAR_ROUNDED,
                label="Prode",
            ),
        ],
        selected_index=selected_index,
        on_change=on_change,
        bgcolor=COLORS["surface"],
        indicator_color=COLORS["primary"] + "33",
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        surface_tint_color=COLORS["surface"],
    )
