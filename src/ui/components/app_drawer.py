import flet as ft
import json
from src.ui.theme import COLORS, toggle_theme, is_dark_mode, app_theme
from src.ui.notifications import (
    EVENTS, is_enabled, set_enabled, is_favorite, toggle_favorite,
    get_favorites, set_favorites, get_event_settings, set_event_settings,
)
from src.ui.flags import get_flag_b64
from src.ui.translations import team_name as _tname

_NOTIF_EVENTS_KEY = "notif_events"
_NOTIF_FAVS_KEY = "notif_favorites"

# Reference to the current view's drawer (updated on each route change)
_drawer: ft.NavigationDrawer | None = None


def build_current_drawer(page: ft.Page, service=None) -> ft.NavigationDrawer:
    """Build a fresh drawer and store it as the current reference.
    Must be called from route_change before appending the view."""
    global _drawer
    _drawer = _build_drawer(page, service)
    return _drawer


def open_drawer(page: ft.Page) -> None:
    if _drawer is not None:
        _drawer.open = True
        page.update()


def build_hamburger(page: ft.Page) -> ft.IconButton:
    return ft.IconButton(
        icon=ft.Icons.MENU_ROUNDED,
        icon_color=COLORS["text_secondary"],
        icon_size=24,
        on_click=lambda _: open_drawer(page),
        tooltip="Menú",
    )


def build_refresh_btn(page: ft.Page, service) -> ft.IconButton:
    """Botón de actualización reutilizable para cualquier pantalla."""
    btn: list = [None]

    async def _on_click(_):
        if btn[0]:
            btn[0].disabled = True
            btn[0].icon = ft.Icons.HOURGLASS_TOP
            page.update()
        try:
            await service.refresh()
        finally:
            if btn[0]:
                btn[0].disabled = False
                btn[0].icon = ft.Icons.REFRESH
                page.update()

    btn[0] = ft.IconButton(
        icon=ft.Icons.REFRESH,
        icon_color=COLORS["text_secondary"],
        icon_size=20,
        tooltip="Actualizar",
        on_click=_on_click,
    )
    return btn[0]


async def open_notif_dialog(page: ft.Page, service=None) -> None:
    # Cargar ajustes guardados
    try:
        saved = await page.client_storage.get_async(_NOTIF_EVENTS_KEY)
        if saved:
            set_event_settings(json.loads(saved))
    except Exception:
        pass

    async def _save_events() -> None:
        try:
            await page.client_storage.set_async(_NOTIF_EVENTS_KEY, json.dumps(get_event_settings()))
        except Exception:
            pass

    event_rows: list[ft.Control] = []
    for etype, icon, label, accent in EVENTS:
        def _make_handler(et: str):
            async def _on_change(e):
                set_enabled(et, e.control.value)
                await _save_events()
            return _on_change

        event_rows.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(icon, size=20),
                    ft.Text(label, size=14, color=COLORS["text"], expand=True),
                    ft.Switch(
                        value=is_enabled(etype),
                        active_color=accent,
                        on_change=_make_handler(etype),
                    ),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=4, vertical=2),
            )
        )

    _dlg_ref: list[ft.AlertDialog] = []

    def _close(_):
        if _dlg_ref:
            page.close(_dlg_ref[0])

    dlg = ft.AlertDialog(
        title=ft.Row([
            ft.Text("🔔", size=20),
            ft.Text("Notificaciones", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
        ], spacing=10),
        content=ft.Container(
            content=ft.Column(
                event_rows,
                spacing=4,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=320,
            height=340,
        ),
        bgcolor=COLORS["surface"],
        actions=[
            ft.TextButton(
                "Listo",
                on_click=_close,
                style=ft.ButtonStyle(color=COLORS["primary"]),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    _dlg_ref.append(dlg)
    page.open(dlg)


async def open_favorites_dialog(page: ft.Page, service=None) -> None:
    # Cargar favoritos guardados
    try:
        saved = await page.client_storage.get_async(_NOTIF_FAVS_KEY)
        if saved:
            set_favorites(json.loads(saved))
    except Exception:
        pass

    async def _save_favs() -> None:
        try:
            await page.client_storage.set_async(_NOTIF_FAVS_KEY, json.dumps(list(get_favorites())))
        except Exception:
            pass

    # Obtener todos los equipos del fixture
    teams: list[str] = []
    if service:
        seen: set[str] = set()
        for m in service.matches:
            for t in (m.home, m.away):
                if t.id != 0 and t.name and t.name not in seen:
                    seen.add(t.name)
                    teams.append(t.name)
        teams.sort(key=lambda n: _tname(n))

    chip_refs: dict[str, ft.Container] = {}

    def _hint_text() -> str:
        n = len([t for t in teams if is_favorite(t)])
        if n == 0:
            return "Sin favoritos — recibirás alertas de todos los partidos"
        return f"{n} equipo{'s' if n != 1 else ''} seleccionado{'s' if n != 1 else ''}"

    fav_count_text = ft.Text(
        _hint_text(),
        size=11,
        color=COLORS["text_secondary"],
        italic=True,
    )

    def _update_hint() -> None:
        fav_count_text.value = _hint_text()

    def _make_chip_click(n: str):
        async def _handler(_):
            toggle_favorite(n)
            c = chip_refs.get(n)
            if c:
                fav = is_favorite(n)
                c.bgcolor = COLORS["primary"] if fav else COLORS["card"]
                c.border = ft.border.all(1, COLORS["primary"] if fav else COLORS["card_border"])
                txt = c.content.controls[-1]
                txt.color = "#FFFFFF" if fav else COLORS["text_secondary"]
            _update_hint()
            await _save_favs()
            page.update()
        return _handler

    chips: list[ft.Control] = []
    for name in teams:
        fav = is_favorite(name)
        b64 = get_flag_b64(name)
        flag_w = (
            ft.Image(src_base64=b64, width=18, height=12, fit=ft.ImageFit.CONTAIN, border_radius=2)
            if b64 else ft.Container(width=18, height=12)
        )
        chip = ft.Container(
            content=ft.Row([
                flag_w,
                ft.Text(
                    _tname(name), size=11,
                    color="#FFFFFF" if fav else COLORS["text_secondary"],
                    no_wrap=True,
                ),
            ], spacing=5, tight=True,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=COLORS["primary"] if fav else COLORS["card"],
            border=ft.border.all(1, COLORS["primary"] if fav else COLORS["card_border"]),
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=8, vertical=5),
            on_click=_make_chip_click(name),
            ink=True,
        )
        chip_refs[name] = chip
        chips.append(chip)

    body: list[ft.Control] = [fav_count_text]
    if chips:
        body.append(
            ft.Container(
                content=ft.Row(chips, wrap=True, spacing=6, run_spacing=6),
                padding=ft.padding.only(top=6),
            )
        )
    else:
        body.append(
            ft.Text("Cargando equipos...", size=11, color=COLORS["text_secondary"], italic=True)
        )

    _dlg_ref: list[ft.AlertDialog] = []

    def _close(_):
        if _dlg_ref:
            page.close(_dlg_ref[0])

    dlg = ft.AlertDialog(
        title=ft.Row([
            ft.Text("⭐", size=20),
            ft.Text("Equipos favoritos", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
        ], spacing=10),
        content=ft.Container(
            content=ft.Column(body, spacing=4, scroll=ft.ScrollMode.AUTO),
            width=320,
            height=440,
        ),
        bgcolor=COLORS["surface"],
        actions=[
            ft.TextButton(
                "Listo",
                on_click=_close,
                style=ft.ButtonStyle(color=COLORS["primary"]),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    _dlg_ref.append(dlg)
    page.open(dlg)


def _build_drawer(page: ft.Page, service=None) -> ft.NavigationDrawer:
    def _nav(route: str):
        def handler(_):
            if _drawer is not None:
                _drawer.open = False
                page.update()
            page.go(route)
        return handler

    async def _on_theme_toggle(_):
        toggle_theme()
        try:
            await page.client_storage.set_async("theme_dark", is_dark_mode())
        except Exception:
            pass
        page.theme_mode = ft.ThemeMode.DARK if is_dark_mode() else ft.ThemeMode.LIGHT
        page.bgcolor = COLORS["bg"]
        page.theme = app_theme()
        page._Page__last_route = None
        page.go(page.route)

    async def _on_notif_tap(_):
        if _drawer is not None:
            _drawer.open = False
            page.update()
        await open_notif_dialog(page, service)

    async def _on_favs_tap(_):
        if _drawer is not None:
            _drawer.open = False
            page.update()
        await open_favorites_dialog(page, service)

    nav_items = [
        (ft.Icons.HOME_ROUNDED,     ft.Icons.HOME_OUTLINED,          "Inicio",   "/"),
        (ft.Icons.SPORTS_SOCCER,    ft.Icons.SPORTS_SOCCER_OUTLINED,  "Fixture",  "/fixtures"),
        (ft.Icons.TABLE_CHART,      ft.Icons.TABLE_CHART_OUTLINED,    "Grupos",   "/standings"),
        (ft.Icons.ACCOUNT_TREE,     ft.Icons.ACCOUNT_TREE_OUTLINED,   "Llaves",   "/bracket"),
        (ft.Icons.STAR_ROUNDED,     ft.Icons.STAR_BORDER_ROUNDED,     "Prode",    "/prode"),
    ]

    current = page.route or "/"
    items: list[ft.Control] = []
    for sel_icon, unsel_icon, label, route in nav_items:
        active = current == route or (route == "/" and current in ("", "/"))
        items.append(
            ft.Container(
                content=ft.Row([
                    ft.Icon(
                        sel_icon if active else unsel_icon,
                        color=COLORS["primary"] if active else COLORS["text_secondary"],
                        size=22,
                    ),
                    ft.Text(
                        label,
                        size=15,
                        color=COLORS["primary"] if active else COLORS["text"],
                        weight=ft.FontWeight.W_600 if active else ft.FontWeight.NORMAL,
                    ),
                ], spacing=16),
                padding=ft.padding.symmetric(horizontal=20, vertical=13),
                bgcolor=COLORS["primary"] + "18" if active else "transparent",
                border_radius=12,
                on_click=_nav(route),
                ink=True,
                margin=ft.margin.symmetric(horizontal=8, vertical=2),
            )
        )

    dark = is_dark_mode()
    theme_row = ft.Container(
        content=ft.Row([
            ft.Icon(
                ft.Icons.DARK_MODE if dark else ft.Icons.LIGHT_MODE,
                color=COLORS["text_secondary"],
                size=22,
            ),
            ft.Text(
                "Modo oscuro" if dark else "Modo claro",
                size=15,
                color=COLORS["text"],
                expand=True,
            ),
            ft.Switch(
                value=dark,
                active_color=COLORS["primary"],
                on_change=_on_theme_toggle,
            ),
        ], spacing=16),
        padding=ft.padding.symmetric(horizontal=20, vertical=10),
        margin=ft.margin.symmetric(horizontal=8, vertical=4),
    )

    notif_row = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.NOTIFICATIONS_OUTLINED, color=COLORS["text_secondary"], size=22),
            ft.Text("Notificaciones", size=15, color=COLORS["text"], expand=True),
            ft.Icon(ft.Icons.CHEVRON_RIGHT, color=COLORS["text_secondary"], size=20),
        ], spacing=16),
        padding=ft.padding.symmetric(horizontal=20, vertical=13),
        margin=ft.margin.symmetric(horizontal=8, vertical=2),
        border_radius=12,
        on_click=_on_notif_tap,
        ink=True,
    )

    favs_row = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.STAR_OUTLINE_ROUNDED, color=COLORS["text_secondary"], size=22),
            ft.Text("Equipos favoritos", size=15, color=COLORS["text"], expand=True),
            ft.Icon(ft.Icons.CHEVRON_RIGHT, color=COLORS["text_secondary"], size=20),
        ], spacing=16),
        padding=ft.padding.symmetric(horizontal=20, vertical=13),
        margin=ft.margin.symmetric(horizontal=8, vertical=2),
        border_radius=12,
        on_click=_on_favs_tap,
        ink=True,
    )

    donate_row = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Text("☕", size=19),
                width=36,
                height=36,
                bgcolor="#FFD60022",
                border_radius=18,
                alignment=ft.alignment.center,
            ),
            ft.Column([
                ft.Text("Apoyar el desarrollo", size=14, color=COLORS["text"],
                        weight=ft.FontWeight.W_500),
                ft.Text("$1 o más · ¡gracias!", size=11, color=COLORS["text_secondary"]),
            ], spacing=1, expand=True, tight=True),
            ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, color="#FFD600", size=16),
        ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.symmetric(horizontal=20, vertical=12),
        margin=ft.margin.only(left=8, right=8, top=4, bottom=8),
        border_radius=12,
        border=ft.border.all(1, "#FFD60035"),
        on_click=lambda _: page.launch_url("https://link.mercadopago.com.ar/maxirojasdev"),
        ink=True,
    )

    return ft.NavigationDrawer(
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Image(src="trophy.png", width=60, height=54, fit=ft.ImageFit.CONTAIN),
                    ft.Text(
                        "MaxFixture",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=COLORS["text"],
                    ),
                    ft.Text("Mundial 2026", size=12, color=COLORS["text_secondary"]),
                ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.only(left=20, top=56, right=20, bottom=20),
                bgcolor=COLORS["surface"],
                alignment=ft.alignment.center,
            ),
            ft.Divider(height=1, color=COLORS["card_border"], thickness=1),
            ft.Container(height=8),
            *items,
            ft.Divider(height=1, color=COLORS["card_border"], thickness=1),
            theme_row,
            notif_row,
            favs_row,
            donate_row,
        ],
        bgcolor=COLORS["surface"],
    )
