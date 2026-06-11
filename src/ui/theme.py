import flet as ft

COLORS_DARK: dict[str, str] = {
    "bg":             "#071428",
    "surface":        "#0D1F3C",
    "card":           "#132B50",
    "primary":        "#2979FF",
    "accent":         "#C8A84B",
    "green":          "#00E676",
    "red":            "#FF1744",
    "yellow":         "#FFD600",
    "text":           "#FFFFFF",
    "text_secondary": "#7A9CC4",
    "live":           "#FF1744",
    "shadow":         "#00000044",
    "card_border":    "#1E4080",
}

COLORS_LIGHT: dict[str, str] = {
    "bg":             "#E8EFF8",
    "surface":        "#FFFFFF",
    "card":           "#FFFFFF",
    "primary":        "#1565C0",
    "accent":         "#B8860B",
    "green":          "#16A34A",
    "red":            "#DC2626",
    "yellow":         "#B45309",
    "text":           "#0A1628",
    "text_secondary": "#4A6FA5",
    "live":           "#DC2626",
    "shadow":         "#0A1A3A26",
    "card_border":    "#BBCDE8",
}

COLORS: dict[str, str] = dict(COLORS_DARK)

_dark: bool = True


def is_dark_mode() -> bool:
    return _dark


def toggle_theme() -> None:
    set_dark_mode(not _dark)


def set_dark_mode(dark: bool) -> None:
    global _dark
    _dark = dark
    COLORS.update(COLORS_DARK if _dark else COLORS_LIGHT)


def build_theme_toggle(page: ft.Page) -> ft.IconButton:
    def _on_click(e: ft.ControlEvent) -> None:
        toggle_theme()
        page.theme_mode = ft.ThemeMode.DARK if _dark else ft.ThemeMode.LIGHT
        page.bgcolor = COLORS["bg"]
        page.go(page.route)

    return ft.IconButton(
        icon=ft.Icons.LIGHT_MODE if _dark else ft.Icons.DARK_MODE,
        icon_color=COLORS["text_secondary"],
        icon_size=22,
        on_click=_on_click,
        tooltip="Modo claro" if _dark else "Modo oscuro",
    )


def app_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=COLORS["primary"],
        color_scheme=ft.ColorScheme(
            primary=COLORS["primary"],
            secondary=COLORS["accent"],
            background=COLORS["bg"],
            surface=COLORS["surface"],
            on_primary="#FFFFFF" if not _dark else "#000000",
            on_background=COLORS["text"],
            on_surface=COLORS["text"],
            # NavigationBar usa secondary_container para el indicador y
            # on_secondary_container para el ícono/label seleccionado
            secondary_container=COLORS["primary"] + "33",
            on_secondary_container=COLORS["text"],
        ),
    )
