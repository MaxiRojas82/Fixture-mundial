import asyncio
import flet as ft
from src.ui.theme import COLORS
from src.ui.notifications import event_icon, event_accent


class GoalAlert(ft.Container):
    def __init__(self, page: ft.Page) -> None:
        self._icon_text = ft.Text("⚽", size=24)
        self._label = ft.Text(
            "",
            size=13,
            color=COLORS["text"],
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        self._tap_hint = ft.Text(
            "Ver partido →",
            size=10,
            color=COLORS["text_secondary"],
            italic=True,
            text_align=ft.TextAlign.CENTER,
        )
        super().__init__(
            content=ft.Column([
                ft.Row(
                    [self._icon_text, self._label],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self._tap_hint,
            ], spacing=3, tight=True,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=COLORS["card"],
            border=ft.border.all(2, COLORS["accent"]),
            border_radius=22,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            visible=False,
            opacity=0,
            animate_opacity=300,
            left=24,
            right=24,
            top=76,
            shadow=ft.BoxShadow(
                blur_radius=20,
                color=COLORS["accent"] + "66",
                offset=ft.Offset(0, 4),
            ),
            ink=True,
        )
        self._page = page
        self._match_id: int | None = None
        self._lock = asyncio.Lock()
        self.on_click = self._on_tap

    def _on_tap(self, _) -> None:
        if self._match_id is not None:
            self._page.go(f"/match/{self._match_id}")

    async def show(self, message: str, event_type: str = "goal", match_id: int | None = None) -> None:
        color = event_accent(event_type)
        icon  = event_icon(event_type)
        async with self._lock:
            self._match_id = match_id
            self._icon_text.value = icon
            self._label.value = message
            self._tap_hint.visible = match_id is not None
            self.border = ft.border.all(2, color)
            self.shadow = ft.BoxShadow(
                blur_radius=20,
                color=color + "66",
                offset=ft.Offset(0, 4),
            )
            self.visible = True
            self.opacity = 1
            self._page.update()
            await asyncio.sleep(4)
            self.opacity = 0
            self._page.update()
            await asyncio.sleep(0.35)
            self.visible = False
            self._page.update()
