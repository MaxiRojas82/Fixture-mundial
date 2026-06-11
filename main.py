import flet as ft


async def main(page: ft.Page) -> None:
    page.bgcolor = "#071428"
    page.padding = 0
    page.title = "MaxFixture Mundial 2026"
    page.theme_mode = ft.ThemeMode.DARK

    # Mostrar pantalla de carga ANTES de cualquier import pesado.
    # Si esto no aparece, el problema es con Flet en sí.
    page.add(ft.Container(
        content=ft.Column([
            ft.ProgressRing(color="#2979FF", width=40, height=40),
            ft.Text("Cargando...", color="#7A9CC4", size=14),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=16),
        alignment=ft.alignment.center,
        expand=True,
    ))
    page.update()

    import asyncio
    await asyncio.sleep(0)  # ceder al event loop para que la pantalla se renderice

    # Configuración de ventana solo en escritorio
    if page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.MACOS, ft.PagePlatform.LINUX):
        try:
            page.window_width = 390
            page.window_height = 844
            page.window_resizable = True
            page.window_icon = "assets/icon.png"
        except Exception:
            pass

    try:
        from src.ui.screens.home_screen import HomeScreen
        from src.ui.screens.fixtures_screen import FixturesScreen
        from src.ui.screens.standings_screen import StandingsScreen
        from src.ui.screens.bracket_screen import BracketScreen
        from src.ui.screens.prode_screen import ProdeScreen
        from src.ui.screens.match_screen import MatchScreen
        from src.ui.theme import app_theme, COLORS, set_dark_mode
        from src.ui.components.app_drawer import build_current_drawer
        from src.services.live_service import LiveService
        from src.services import push_notification_service as push_notif

        # Restaurar el tema elegido por el usuario (oscuro por defecto)
        try:
            saved_dark = await page.client_storage.get_async("theme_dark")
        except Exception:
            saved_dark = None
        if saved_dark is False:
            set_dark_mode(False)
            page.theme_mode = ft.ThemeMode.LIGHT

        page.theme = app_theme()
        page.bgcolor = COLORS["bg"]

        live_service = LiveService()
        push_notif.init(page)

        async def route_change(e: ft.RouteChangeEvent) -> None:
            try:
                route = page.route or "/"

                if route.startswith("/match/"):
                    # Push sobre el stack existente para preservar historial de navegación
                    try:
                        match_id = int(route.split("/")[-1])
                        v = MatchScreen(page, live_service, match_id).build()
                    except (ValueError, IndexError):
                        page.go("/")
                        return
                else:
                    page.views.clear()
                    if route in ("/", ""):
                        v = HomeScreen(page, live_service).build()
                    elif route == "/fixtures":
                        v = FixturesScreen(page, live_service).build()
                    elif route == "/standings":
                        v = StandingsScreen(page, live_service).build()
                    elif route == "/bracket":
                        v = BracketScreen(page, live_service).build()
                    elif route == "/prode":
                        v = ProdeScreen(page, live_service).build()
                    else:
                        page.go("/")
                        return
                    v.drawer = build_current_drawer(page, live_service)

                page.views.append(v)
                page.update()
            except Exception as _exc:
                import traceback as _tb
                page.views.clear()
                page.views.append(ft.View(
                    route=page.route or "/",
                    controls=[ft.Container(
                        content=ft.Column([
                            ft.Text("ERROR DE PANTALLA", size=16, weight=ft.FontWeight.BOLD, color="#FF4444"),
                            ft.Text(str(_exc), size=12, color="#FF8888"),
                            ft.Text(_tb.format_exc(), size=9, color="#AAAAAA", selectable=True),
                        ], scroll=ft.ScrollMode.AUTO, spacing=8),
                        padding=ft.padding.all(20),
                        expand=True,
                    )],
                    bgcolor="#071428",
                    padding=0,
                ))
                page.update()

        async def view_pop(e: ft.ViewPopEvent) -> None:
            if len(page.views) > 1:
                page.views.pop()
                page.update()
            else:
                page.go("/")

        page.on_route_change = route_change
        page.on_view_pop = view_pop

        page.controls.clear()
        page.go(page.route or "/")
        asyncio.create_task(live_service.start())

    except Exception as exc:
        import traceback
        error_text = traceback.format_exc()
        page.controls.clear()
        page.views.clear()
        page.add(ft.Container(
            content=ft.Column([
                ft.Text("ERROR AL INICIAR", size=18, weight=ft.FontWeight.BOLD, color="#FF4444"),
                ft.Text(str(exc), size=13, color="#FF8888"),
                ft.Divider(color="#333333"),
                ft.Text(error_text, size=10, color="#AAAAAA", selectable=True),
            ], scroll=ft.ScrollMode.AUTO, spacing=8),
            padding=ft.padding.all(20),
            expand=True,
        ))
        page.update()


ft.app(target=main)
