import flet as ft

_page: ft.Page | None = None


def init(page: ft.Page) -> None:
    """Registrar la página al arrancar. Escucha eventos desde Dart."""
    global _page
    _page = page
    page.on_invoke = _on_invoke


def show(title: str, body: str, match_id: int) -> None:
    """Mostrar notificación del sistema cuando la app está en foreground.
    En background/cerrada el servidor FCM la envía directamente al dispositivo."""
    if _page is None:
        return
    try:
        _page.invoke_method(
            "showNotification",
            {"title": title, "body": body, "matchId": str(match_id)},
        )
    except Exception:
        pass


def _on_invoke(e: ft.InvokeMethodEvent) -> None:
    """Recibir llamadas desde Dart:
      - 'showNotification': mostrar notificación local (cuando app en foreground)
      - 'navigateTo':       navegar al partido al tocar una notificación FCM
    """
    if _page is None:
        return
    try:
        data = e.data if isinstance(e.data, dict) else {}
        if e.name == "navigateTo":
            route = data.get("route", "")
            if route:
                _page.go(route)
    except Exception:
        pass
