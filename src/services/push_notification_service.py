import flet as ft

_page: ft.Page | None = None


def init(page: ft.Page) -> None:
    """Registrar la página al arrancar. Escucha eventos desde Dart."""
    global _page
    _page = page
    try:
        page.on_invoke = _on_invoke  # type: ignore[attr-defined]
    except Exception:
        pass


def show(title: str, body: str, match_id: int) -> None:
    """Mostrar notificación del sistema cuando la app está en foreground."""
    if _page is None:
        return
    try:
        _page.invoke_method(
            "showNotification",
            {"title": title, "body": body, "matchId": str(match_id)},
        )
    except Exception:
        pass


def _on_invoke(e) -> None:  # type: ignore[no-untyped-def]
    """Recibir llamadas desde Dart (navigateTo, showNotification)."""
    if _page is None:
        return
    try:
        data = e.data if isinstance(e.data, dict) else {}
        name = getattr(e, "name", None) or getattr(e, "method_name", None) or ""
        if name == "navigateTo":
            route = data.get("route", "")
            if route:
                _page.go(route)
    except Exception:
        pass
