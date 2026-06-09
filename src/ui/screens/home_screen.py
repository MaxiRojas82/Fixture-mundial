import asyncio
from datetime import datetime, timezone, timedelta
from datetime import date as DateType
import flet as ft
from src.services.live_service import LiveService
from src.models.match import Match
from src.ui.notifications import is_enabled, notifications_enabled, toggle_notifications
from src.ui.theme import COLORS
from src.ui.components.app_drawer import build_hamburger, build_refresh_btn, open_notif_dialog
from src.services import push_notification_service as push_notif
from src.ui.components.match_card import build_match_card
from src.ui.components.goal_alert import GoalAlert
from src.ui.components.nav_bar import build_nav_bar


# Fecha seleccionada persiste entre reconstrucciones de la vista
_selected_date: DateType = DateType.today()


class HomeScreen:
    def __init__(self, page: ft.Page, live_service: LiveService) -> None:
        self._page = page
        self._service = live_service
        self._goal_alert = GoalAlert(page)
        self._body = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

        # Widgets del countdown (reutilizados entre renders)
        self._cd_days  = ft.Text("--", size=38, weight=ft.FontWeight.BOLD, color=COLORS["primary"])
        self._cd_hours = ft.Text("--", size=38, weight=ft.FontWeight.BOLD, color=COLORS["primary"])
        self._cd_mins  = ft.Text("--", size=38, weight=ft.FontWeight.BOLD, color=COLORS["primary"])
        self._cd_secs  = ft.Text("--", size=38, weight=ft.FontWeight.BOLD, color=COLORS["text_secondary"])

        # Row persistente para tabs de fecha — preserva scroll entre renders
        self._date_row = ft.Row([], spacing=8, scroll=ft.ScrollMode.AUTO)
        self._date_container = ft.Container(
            content=self._date_row,
            padding=ft.padding.only(left=16, right=16, top=10, bottom=4),
        )

    # ── Build ──────────────────────────────────────────────────────────────

    def build(self) -> ft.View:
        self._service.on_event(self._on_event)
        self._service.on_update(self._on_update)
        self._refresh_btn = build_refresh_btn(self._page, self._service)
        self._notif_btn = ft.IconButton(
            icon=ft.Icons.NOTIFICATIONS_ROUNDED if notifications_enabled() else ft.Icons.NOTIFICATIONS_OFF_ROUNDED,
            icon_color=COLORS["primary"] if notifications_enabled() else COLORS["text_secondary"],
            icon_size=22,
            tooltip="Notificaciones activadas" if notifications_enabled() else "Notificaciones desactivadas",
            on_click=self._toggle_notif,
        )
        self._render()
        asyncio.create_task(self._run_countdown())

        return ft.View(
            route="/",
            controls=[
                ft.Stack([
                    ft.Column([
                        self._build_header(),
                        self._body,
                    ], expand=True, spacing=0),
                    self._goal_alert,
                ], expand=True),
            ],
            navigation_bar=build_nav_bar(self._page, 0),
            bgcolor=COLORS["bg"],
            padding=0,
        )

    def _build_header(self) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                build_hamburger(self._page),
                ft.Image(src="trophy.png", width=40, height=36, fit=ft.ImageFit.CONTAIN),
                ft.Column([
                    ft.Text(
                        "MaxFixture Mundial 2026",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=COLORS["text"],
                    ),
                    ft.Row([
                        ft.Container(width=6, height=6, bgcolor=COLORS["live"], border_radius=3),
                        ft.Text("Tiempo real", size=11, color=COLORS["text_secondary"]),
                    ], spacing=5),
                ], spacing=2, expand=True),
                self._refresh_btn,
                self._notif_btn,
            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=8, top=52, right=16, bottom=14),
            bgcolor=COLORS["surface"],
            shadow=ft.BoxShadow(blur_radius=8, color=COLORS["shadow"], offset=ft.Offset(0, 2)),
        )

    def _build_countdown_card(self) -> ft.Control:
        def _unit(num: ft.Text, label: str) -> ft.Row:
            return ft.Row([
                num,
                ft.Text(label, size=13, color=COLORS["text_secondary"], weight=ft.FontWeight.BOLD),
            ], spacing=3, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        colon = lambda: ft.Text(":", size=28, weight=ft.FontWeight.BOLD, color=COLORS["primary"])

        return ft.Container(
            alignment=ft.alignment.center,
            content=ft.Column([
                ft.Image(src="trophy.png", width=160, height=140, fit=ft.ImageFit.CONTAIN),
                ft.Text(
                    "MAXFIXTURE MUNDIAL 2026",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=COLORS["text"],
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=4),
                ft.Text(
                    "FALTA PARA EL MUNDIAL",
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color=COLORS["text_secondary"],
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=12),
                ft.Row([
                    _unit(self._cd_days, "d"),
                    colon(),
                    _unit(self._cd_hours, "h"),
                    colon(),
                    _unit(self._cd_mins, "m"),
                    colon(),
                    _unit(self._cd_secs, "s"),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=16),
                ft.Container(
                    content=ft.Text(
                        "11 de junio · Toronto",
                        size=12,
                        color=COLORS["text_secondary"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    bgcolor=COLORS["card_border"] + "88",
                    border_radius=20,
                    padding=ft.padding.symmetric(horizontal=16, vertical=6),
                ),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
        )

    def _build_date_tabs(self) -> None:
        """Actualiza self._date_row.controls sin recrear el widget (preserva scroll)."""
        today = DateType.today()
        tomorrow = today + timedelta(days=1)
        day_abbr = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

        match_dates = set(m.date.astimezone().date() for m in self._service.matches)
        available = sorted(match_dates | {today})

        tabs: list[ft.Control] = []
        for d in available:
            if d == today:
                label = "Hoy"
            elif d == tomorrow:
                label = "Mañana"
            else:
                label = f"{day_abbr[d.weekday()]} {d.day}"

            is_sel = (d == _selected_date)

            def _on_tab(_, date=d) -> None:
                global _selected_date
                _selected_date = date
                self._render()
                self._page.update()

            tabs.append(
                ft.Container(
                    content=ft.Text(
                        label,
                        size=12,
                        weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.NORMAL,
                        color="#FFFFFF" if is_sel else COLORS["text_secondary"],
                    ),
                    bgcolor=COLORS["primary"] if is_sel else COLORS["card"],
                    border=ft.border.all(1, COLORS["primary"] if is_sel else COLORS["card_border"]),
                    border_radius=20,
                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    on_click=_on_tab,
                    ink=True,
                    shadow=ft.BoxShadow(
                        blur_radius=8,
                        color=COLORS["primary"] + "44",
                        offset=ft.Offset(0, 2),
                    ) if is_sel else None,
                )
            )

        self._date_row.controls = tabs

    # ── Render y datos ─────────────────────────────────────────────────────

    def _toggle_notif(self, _) -> None:
        enabled = toggle_notifications()
        self._notif_btn.icon = ft.Icons.NOTIFICATIONS_ROUNDED if enabled else ft.Icons.NOTIFICATIONS_OFF_ROUNDED
        self._notif_btn.icon_color = COLORS["primary"] if enabled else COLORS["text_secondary"]
        self._notif_btn.tooltip = "Notificaciones activadas" if enabled else "Notificaciones desactivadas"
        self._page.update()

    def _render(self) -> None:
        self._body.controls.clear()
        self._body.scroll = ft.ScrollMode.AUTO
        self._body.alignment = ft.MainAxisAlignment.START

        wc_start = self._get_wc_start()
        before_wc = wc_start and datetime.now(timezone.utc) < wc_start
        today = DateType.today()

        # Tabs siempre visibles (reutiliza el mismo Row para no resetear scroll)
        self._build_date_tabs()
        self._body.controls.append(self._date_container)

        # Si el tab seleccionado es hoy y aún no empezó el Mundial → countdown
        if before_wc and _selected_date == today:
            self._body.controls.append(self._build_countdown_card())
            return

        # Partidos filtrados por día
        all_matches = self._service.matches
        day_matches = [m for m in all_matches if m.date.astimezone().date() == _selected_date]
        live     = [m for m in day_matches if m.is_live]
        non_live = [m for m in day_matches if not m.is_live]

        if live:
            self._body.controls.append(_section_label("EN VIVO", color=COLORS["live"]))
            for m in live:
                self._body.controls.append(
                    build_match_card(m, on_tap=lambda _, mid=m.id: self._page.go(f"/match/{mid}"))
                )

        if non_live:
            self._body.controls.append(_section_label("PARTIDOS DEL DÍA"))
            for m in non_live:
                self._body.controls.append(
                    build_match_card(m, on_tap=lambda _, mid=m.id: self._page.go(f"/match/{mid}"))
                )

        if not live and not non_live:
            err = self._service.load_error
            if err and not self._service.matches:
                msg = ft.Column([
                    ft.Text("⚠️", size=40, text_align=ft.TextAlign.CENTER),
                    ft.Text("No se pudieron cargar los partidos",
                           color=COLORS["text_secondary"],
                           text_align=ft.TextAlign.CENTER, size=14),
                    ft.Text(err, color=COLORS["red"], text_align=ft.TextAlign.CENTER,
                           size=10, selectable=True),
                    ft.Text("Tocá 🔄 para reintentar", color=COLORS["text_secondary"],
                           text_align=ft.TextAlign.CENTER, size=12, italic=True),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
            else:
                msg = ft.Column([
                    ft.Text("⚽", size=52, text_align=ft.TextAlign.CENTER),
                    ft.Text("No hay partidos este día",
                           color=COLORS["text_secondary"],
                           text_align=ft.TextAlign.CENTER, size=14),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
            self._body.controls.append(
                ft.Container(
                    content=msg,
                    padding=ft.padding.symmetric(vertical=60),
                    alignment=ft.alignment.center,
                )
            )

    def _get_wc_start(self) -> datetime | None:
        matches = self._service.matches
        if matches:
            return min(m.date for m in matches)
        return datetime(2026, 6, 11, 0, 0, 0, tzinfo=timezone.utc)

    # ── Countdown loop ─────────────────────────────────────────────────────

    async def _run_countdown(self) -> None:
        target = self._get_wc_start()
        if not target:
            return
        while True:
            now = datetime.now(timezone.utc)
            delta = target - now
            if delta.total_seconds() <= 0:
                break
            total = int(delta.total_seconds())
            self._cd_days.value  = f"{total // 86400:02d}"
            self._cd_hours.value = f"{(total % 86400) // 3600:02d}"
            self._cd_mins.value  = f"{(total % 3600) // 60:02d}"
            self._cd_secs.value  = f"{total % 60:02d}"
            try:
                self._page.update()
            except Exception:
                break
            await asyncio.sleep(1)

    # ── Callbacks ──────────────────────────────────────────────────────────

    def _on_update(self) -> None:
        self._render()
        self._page.update()

    def _on_event(self, match: Match, text: str, event_type: str) -> None:
        if is_enabled(event_type):
            asyncio.create_task(self._goal_alert.show(text, event_type, match_id=match.id))
            push_notif.show(
                title=_event_title(event_type, match),
                body=text.lstrip("⚽🎯▶️⏸🏁🟨🟥 "),
                match_id=match.id,
            )


def _event_title(event_type: str, match: Match) -> str:
    titles = {
        "goal":        "⚽ ¡Gol!",
        "penalty":     "🎯 ¡Penal!",
        "kickoff":     "▶️ Partido iniciado",
        "halftime":    "⏸ Medio tiempo",
        "fulltime":    "🏁 Partido finalizado",
        "yellow_card": "🟨 Tarjeta amarilla",
        "red_card":    "🟥 Tarjeta roja",
    }
    base = titles.get(event_type, "🔔 Evento")
    return f"{base} — {match.home.name} vs {match.away.name}"


def _section_label(text: str, color: str | None = None) -> ft.Container:
    c = color or COLORS["text_secondary"]
    return ft.Container(
        content=ft.Row([
            ft.Container(width=3, height=14, bgcolor=c, border_radius=2),
            ft.Text(text, size=11, weight=ft.FontWeight.BOLD, color=c),
        ], spacing=8),
        padding=ft.padding.only(left=16, top=18, right=20, bottom=6),
    )
