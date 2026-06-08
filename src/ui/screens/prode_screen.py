import asyncio
import uuid
import json
import random
import string
import urllib.parse
from datetime import datetime, timezone, timedelta
from datetime import date as DateType

import flet as ft
from src.services.live_service import LiveService
from src.models.match import Match, MatchStatus
from src.models.prode import ProdeUser, ProdeGroup, Prediction, LeaderboardEntry, calc_points
import src.services.prode_service as firebase
from src.ui.theme import COLORS
from src.ui.components.nav_bar import build_nav_bar
from src.ui.components.app_drawer import build_hamburger, build_refresh_btn
from src.ui.translations import team_name
from src.ui.flags import get_flag_url, get_flag_b64


def _gen_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _teams_known(m: Match) -> bool:
    """True cuando ambos equipos ya están definidos (no TBD)."""
    return m.home.id != 0 and m.away.id != 0


def _can_predict(m: Match) -> bool:
    if not _teams_known(m):
        return False
    return (
        m.status == MatchStatus.SCHEDULED
        and m.date > datetime.now(timezone.utc) + timedelta(hours=1)
    )


def _flag(name: str, team_id: int = 0, size: int = 26) -> ft.Control:
    h = round(size * 0.67)
    if team_id == 0:
        return ft.Container(
            content=ft.Text("?", size=max(8, size // 3),
                           color=COLORS["text_secondary"]),
            width=size, height=h,
            bgcolor=COLORS["card_border"],
            border_radius=3,
            alignment=ft.alignment.center,
        )
    b64 = get_flag_b64(name)
    if b64:
        return ft.Image(src_base64=b64, width=size, height=h,
                       fit=ft.ImageFit.CONTAIN, border_radius=3)
    url = get_flag_url(name, 48)
    if not url:
        initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
        return ft.Container(
            content=ft.Text(initials, size=max(7, size // 3),
                           color=COLORS["primary"], weight=ft.FontWeight.BOLD),
            width=size, height=h,
            bgcolor=COLORS["primary"] + "22",
            border_radius=3,
            alignment=ft.alignment.center,
        )
    return ft.Image(
        src=url, width=size, height=h,
        fit=ft.ImageFit.CONTAIN, border_radius=3,
        error_content=ft.Container(
            content=ft.Text(name[:2].upper(), size=max(7, size // 3),
                           color=COLORS["primary"]),
            alignment=ft.alignment.center,
        ),
        gapless_playback=True,
    )


class ProdeScreen:
    _UID   = "prode_uid"
    _NAME  = "prode_name"
    _GROUP = "prode_group"
    _PREDS = "prode_preds"

    def __init__(self, page: ft.Page, live_service: LiveService) -> None:
        self._page = page
        self._service = live_service
        self._user: ProdeUser | None = None
        self._group: ProdeGroup | None = None
        self._preds: dict[int, tuple[int, int]] = {}
        self._leaderboard: list[LeaderboardEntry] = []

        self._header_name = ft.Text("Prode", size=18, weight=ft.FontWeight.BOLD, color=COLORS["text"])
        self._header_sub  = ft.Text("", size=11, color=COLORS["text_secondary"])
        self._banner_row  = ft.Row([], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                   vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self._preds_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self._tabla_col = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

    def build(self) -> ft.View:
        self._service.on_update(self._on_live_update)

        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            tabs=[
                ft.Tab(text="Pronósticos", content=self._preds_col),
                ft.Tab(text="Tabla",        content=self._tabla_col),
            ],
            label_color=COLORS["primary"],
            unselected_label_color=COLORS["text_secondary"],
            indicator_color=COLORS["primary"],
            expand=True,
        )

        view = ft.View(
            route="/prode",
            controls=[
                ft.Column([
                    self._build_topbar(),
                    ft.Container(
                        content=self._banner_row,
                        padding=ft.padding.symmetric(horizontal=16, vertical=8),
                        bgcolor=COLORS["card"],
                        border=ft.border.only(bottom=ft.BorderSide(1, COLORS["card_border"])),
                    ),
                    tabs,
                ], expand=True, spacing=0),
            ],
            navigation_bar=build_nav_bar(self._page, 4),
            bgcolor=COLORS["bg"],
            padding=0,
        )
        asyncio.create_task(self._load())
        return view

    def _build_topbar(self) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                build_hamburger(self._page),
                ft.Container(
                    content=ft.Text("🎯", size=20),
                    bgcolor=COLORS["primary"] + "22",
                    border_radius=8,
                    padding=ft.padding.all(6),
                ),
                ft.Column([self._header_name, self._header_sub], spacing=2, expand=True),
                build_refresh_btn(self._page, self._service),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=8, top=52, right=8, bottom=14),
            bgcolor=COLORS["surface"],
            shadow=ft.BoxShadow(blur_radius=8, color=COLORS["shadow"], offset=ft.Offset(0, 2)),
        )

    # ── Load ──────────────────────────────────────────────────────────────────

    async def _load(self) -> None:
        uid  = await self._page.client_storage.get_async(self._UID)
        name = await self._page.client_storage.get_async(self._NAME)
        code = await self._page.client_storage.get_async(self._GROUP) or ""

        if not uid or not name:
            self._show_setup()
            return

        raw = await self._page.client_storage.get_async(self._PREDS) or "{}"
        try:
            self._preds = {int(k): tuple(v) for k, v in json.loads(raw).items()}
        except Exception:
            self._preds = {}

        self._user = ProdeUser(id=uid, display_name=name, group_code=code)

        if code:
            try:
                self._group = await firebase.get_group(code)
                if self._group is None:
                    await self._page.client_storage.set_async(self._GROUP, "")
                    self._user.group_code = ""
            except Exception:
                pass

        self._render_header()
        self._render_banner()
        self._render_preds()
        self._render_tabla()
        self._page.update()

        if self._group:
            await self._load_leaderboard()

    async def _load_leaderboard(self) -> None:
        if not self._group or not self._user:
            return
        try:
            all_preds = await firebase.get_predictions_for_users(self._group.member_ids)
        except Exception:
            return

        finished = [
            m for m in self._service.matches
            if m.status == MatchStatus.FINISHED and m.score.home is not None
        ]

        board: dict[str, LeaderboardEntry] = {
            uid: LeaderboardEntry(
                user_id=uid,
                display_name=self._group.member_names.get(uid, uid[:6]),
            )
            for uid in self._group.member_ids
        }

        for pred in all_preds:
            match = next((m for m in finished if m.id == pred.match_id), None)
            if not match or match.score.home is None or match.score.away is None:
                continue
            entry = board.get(pred.user_id)
            if not entry:
                continue
            pts = calc_points(pred.home_goals, pred.away_goals, match.score.home, match.score.away)
            entry.points += pts
            if pts == 3:
                entry.exact += 1
            elif pts == 2:
                entry.correct += 1

        self._leaderboard = sorted(board.values(), key=lambda e: (-e.points, -e.exact))
        self._render_tabla()
        self._page.update()

    # ── Render ────────────────────────────────────────────────────────────────

    def _my_points(self) -> int:
        total = 0
        for m in self._service.matches:
            if m.status != MatchStatus.FINISHED or m.score.home is None:
                continue
            pred = self._preds.get(m.id)
            if pred:
                total += calc_points(pred[0], pred[1], m.score.home, m.score.away)
        return total

    def _render_header(self) -> None:
        if not self._user:
            return
        pts = self._my_points()
        n = len(self._preds)
        self._header_sub.value = (
            f"{self._user.display_name}  ·  {pts} pts  ·  "
            f"{n} pronosticado{'s' if n != 1 else ''}"
        )

    def _render_banner(self) -> None:
        if not self._user:
            self._banner_row.controls = []
            return
        if self._group:
            self._banner_row.controls = [
                ft.Column([
                    ft.Text(self._group.name, size=14,
                           weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.Text(
                        f"Código: {self._group.code}  ·  "
                        f"{len(self._group.member_ids)} miembro"
                        f"{'s' if len(self._group.member_ids) != 1 else ''}",
                        size=11, color=COLORS["text_secondary"],
                    ),
                ], spacing=2, expand=True),
                ft.ElevatedButton(
                    "Compartir",
                    icon=ft.Icons.IOS_SHARE,
                    color=COLORS["primary"],
                    bgcolor=COLORS["primary"] + "15",
                    on_click=self._share,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        side=ft.BorderSide(1, COLORS["primary"] + "55"),
                    ),
                    height=36,
                ),
            ]
        else:
            self._banner_row.controls = [
                ft.Text("Sin grupo", size=13, color=COLORS["text_secondary"], expand=True),
                ft.TextButton("+ Crear", on_click=self._dlg_create,
                             style=ft.ButtonStyle(color=COLORS["primary"])),
                ft.TextButton("Unirse", on_click=self._dlg_join,
                             style=ft.ButtonStyle(color=COLORS["text_secondary"])),
            ]

    def _build_scoring_info(self) -> ft.Container:
        def _row(icon: str, label: str, pts: str, pts_color: str) -> ft.Row:
            return ft.Row([
                ft.Text(icon, size=14, width=22),
                ft.Text(label, size=12, color=COLORS["text"], expand=True),
                ft.Container(
                    content=ft.Text(pts, size=11, color=pts_color,
                                   weight=ft.FontWeight.BOLD),
                    bgcolor=pts_color + "22",
                    border_radius=5,
                    padding=ft.padding.symmetric(horizontal=7, vertical=2),
                ),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=COLORS["primary"]),
                    ft.Text("¿Cómo se puntúa?", size=12,
                            weight=ft.FontWeight.BOLD, color=COLORS["primary"]),
                ], spacing=6),
                _row("🎯", "Marcador exacto", "+3 pts", COLORS["green"]),
                _row("✅", "Resultado acertado (G/E/P)", "+2 pts", COLORS["primary"]),
                _row("❌", "Sin acierto", "0 pts", COLORS["red"]),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.LOCK_CLOCK, size=13, color=COLORS["text_secondary"]),
                        ft.Text("Podés modificar hasta 1 hora antes del partido",
                               size=11, color=COLORS["text_secondary"]),
                    ], spacing=5),
                    padding=ft.padding.only(top=4),
                ),
            ], spacing=7, tight=True),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            margin=ft.margin.only(left=16, right=16, top=12, bottom=4),
            bgcolor=COLORS["primary"] + "0D",
            border_radius=12,
            border=ft.border.all(1, COLORS["primary"] + "33"),
        )

    def _render_preds(self) -> None:
        self._preds_col.controls.clear()
        matches = self._service.matches

        self._preds_col.controls.append(self._build_scoring_info())

        if not matches:
            self._preds_col.controls.append(
                ft.Container(
                    content=ft.Text("Cargando partidos...", color=COLORS["text_secondary"]),
                    padding=ft.padding.all(40),
                    alignment=ft.alignment.center,
                )
            )
            return

        by_date: dict[DateType, list[Match]] = {}
        for m in matches:
            d = m.date.astimezone().date()
            by_date.setdefault(d, []).append(m)

        days   = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        months = ["", "ene", "feb", "mar", "abr", "may", "jun",
                  "jul", "ago", "sep", "oct", "nov", "dic"]

        for d in sorted(by_date):
            lbl = f"{days[d.weekday()]} {d.day} {months[d.month]}".upper()
            self._preds_col.controls.append(_section_lbl(lbl))
            for m in sorted(by_date[d], key=lambda x: x.date):
                self._preds_col.controls.append(self._pred_card(m))

        self._preds_col.controls.append(ft.Container(height=16))

    def _render_tabla(self) -> None:
        self._tabla_col.controls.clear()

        if not self._user:
            return

        if not self._group:
            self._tabla_col.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text("👥", size=48, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            "Creá o uníte a un grupo\npara ver la tabla de puntajes",
                            size=14, color=COLORS["text_secondary"],
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=4),
                        ft.FilledButton(
                            "Crear grupo", icon=ft.Icons.ADD,
                            on_click=self._dlg_create,
                            style=ft.ButtonStyle(bgcolor=COLORS["primary"]),
                        ),
                        ft.TextButton(
                            "Unirse con código", on_click=self._dlg_join,
                            style=ft.ButtonStyle(color=COLORS["primary"]),
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10, tight=True),
                    padding=ft.padding.all(48),
                    alignment=ft.alignment.center,
                )
            )
            return

        if not self._leaderboard:
            entries: list[LeaderboardEntry] = [LeaderboardEntry(
                user_id=self._user.id,
                display_name=self._user.display_name,
                points=self._my_points(),
            )]
        else:
            entries = self._leaderboard

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        rows: list[ft.Control] = [
            ft.Row([
                ft.Container(width=36),
                ft.Text("Jugador", size=11, color=COLORS["text_secondary"], expand=True),
                ft.Text("Pts", size=11, color=COLORS["text_secondary"],
                       width=40, text_align=ft.TextAlign.CENTER),
                ft.Text("🎯", size=13, width=30, text_align=ft.TextAlign.CENTER),
                ft.Text("✅", size=13, width=30, text_align=ft.TextAlign.CENTER),
            ], spacing=4),
            ft.Divider(color=COLORS["card_border"], height=1),
        ]

        for i, e in enumerate(entries):
            is_me = e.user_id == self._user.id
            rows.append(ft.Container(
                content=ft.Row([
                    ft.Text(medals.get(i + 1, str(i + 1)), size=14, width=36,
                           text_align=ft.TextAlign.CENTER),
                    ft.Text(
                        e.display_name + (" ★" if is_me else ""),
                        size=13,
                        color=COLORS["primary"] if is_me else COLORS["text"],
                        weight=ft.FontWeight.BOLD if is_me else ft.FontWeight.W_400,
                        expand=True,
                    ),
                    ft.Text(str(e.points), size=14, width=40,
                           weight=ft.FontWeight.BOLD, color=COLORS["text"],
                           text_align=ft.TextAlign.CENTER),
                    ft.Text(str(e.exact), size=12, width=30,
                           color=COLORS["green"], text_align=ft.TextAlign.CENTER),
                    ft.Text(str(e.correct), size=12, width=30,
                           color=COLORS["primary"], text_align=ft.TextAlign.CENTER),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(vertical=6, horizontal=4),
                bgcolor=COLORS["primary"] + "11" if is_me else None,
                border_radius=8,
            ))

        self._tabla_col.controls.append(
            ft.Container(
                content=ft.Column(rows, spacing=6),
                padding=ft.padding.all(16),
                margin=ft.margin.all(16),
                bgcolor=COLORS["card"],
                border_radius=14,
                border=ft.border.all(1, COLORS["card_border"]),
            )
        )

    # ── Match card ────────────────────────────────────────────────────────────

    def _pred_card(self, m: Match) -> ft.Container:
        pred     = self._preds.get(m.id)
        can_edit = _can_predict(m)
        known    = _teams_known(m)

        if m.is_live:
            chip, chip_c = f"🔴 {m.elapsed}'", COLORS["live"]
        elif m.status == MatchStatus.FINISHED:
            chip, chip_c = f"FT  {m.score.home}–{m.score.away}", COLORS["text_secondary"]
        elif m.status == MatchStatus.HALFTIME:
            chip, chip_c = "HT", COLORS["yellow"]
        elif not known:
            chip, chip_c = m.date.astimezone().strftime("%d/%m %H:%M"), COLORS["text_secondary"]
        elif not can_edit and m.status == MatchStatus.SCHEDULED:
            chip, chip_c = f"🔒 {m.date.astimezone().strftime('%H:%M')}", COLORS["text_secondary"]
        else:
            chip, chip_c = m.date.astimezone().strftime("%H:%M"), COLORS["text_secondary"]

        pts_widget = None
        if m.status == MatchStatus.FINISHED and pred and m.score.home is not None and m.score.away is not None:
            pts = calc_points(pred[0], pred[1], m.score.home, m.score.away)
            if pts == 3:
                pts_widget = ft.Text("🎯 ¡Marcador exacto! +3 pts", size=11,
                                    color=COLORS["green"], weight=ft.FontWeight.BOLD)
            elif pts == 2:
                pts_widget = ft.Text("✅ Resultado acertado +2 pts", size=11,
                                    color=COLORS["primary"], weight=ft.FontWeight.BOLD)
            else:
                pts_widget = ft.Text("❌ 0 pts", size=11, color=COLORS["red"])

        home_color = COLORS["text"] if known else COLORS["text_secondary"]
        away_color = COLORS["text"] if known else COLORS["text_secondary"]

        # Widget central: marcador pronosticado o "vs"
        if pred is not None:
            def _score_chip(val: int) -> ft.Container:
                return ft.Container(
                    content=ft.Text(str(val), size=15, weight=ft.FontWeight.BOLD,
                                   color=COLORS["primary"]),
                    bgcolor=COLORS["primary"] + "20",
                    border_radius=6,
                    padding=ft.padding.symmetric(horizontal=9, vertical=3),
                )
            center_widget = ft.Row([
                _score_chip(pred[0]),
                ft.Text("vs", size=10, color=COLORS["text_secondary"]),
                _score_chip(pred[1]),
            ], spacing=5, tight=True,
               vertical_alignment=ft.CrossAxisAlignment.CENTER)
        else:
            center_widget = ft.Text("vs", size=12, color=COLORS["text_secondary"],
                                   width=28, text_align=ft.TextAlign.CENTER)

        rows: list[ft.Control] = [
            ft.Row([
                ft.Text(chip, size=11, color=chip_c, weight=ft.FontWeight.BOLD),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([
                ft.Row([
                    _flag(m.home.name, m.home.id, 24),
                    ft.Text(team_name(m.home.name), size=13, color=home_color,
                           weight=ft.FontWeight.W_500, expand=True, no_wrap=True),
                ], spacing=6, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                center_widget,
                ft.Row([
                    ft.Text(team_name(m.away.name), size=13, color=away_color,
                           weight=ft.FontWeight.W_500, expand=True,
                           text_align=ft.TextAlign.RIGHT, no_wrap=True),
                    _flag(m.away.name, m.away.id, 24),
                ], spacing=6, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                   alignment=ft.MainAxisAlignment.END),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ]

        if pts_widget:
            rows.append(pts_widget)
        elif not known:
            rows.append(ft.Text("🔒 Equipos por definirse", size=11,
                               color=COLORS["text_secondary"], italic=True))
        elif pred is None and can_edit:
            rows.append(ft.Text("Tocá para cargar pronóstico →", size=11,
                               color=COLORS["text_secondary"], italic=True))

        if m.status == MatchStatus.FINISHED and pred and m.score.home is not None and m.score.away is not None:
            pts = calc_points(pred[0], pred[1], m.score.home, m.score.away)
            border = COLORS["green"] + "66" if pts >= 2 else COLORS["red"] + "44"
        elif pred and can_edit:
            border = COLORS["primary"] + "55"
        elif not known:
            border = COLORS["card_border"] + "55" if len(COLORS["card_border"]) == 7 else COLORS["card_border"]
        else:
            border = COLORS["card_border"]

        return ft.Container(
            content=ft.Column(rows, spacing=8),
            padding=ft.padding.all(14),
            margin=ft.margin.symmetric(horizontal=16, vertical=4),
            bgcolor=COLORS["card"],
            border_radius=14,
            border=ft.border.all(1, border),
            shadow=ft.BoxShadow(blur_radius=8, color=COLORS["shadow"], offset=ft.Offset(0, 2)),
            opacity=0.55 if not known else 1.0,
            on_click=(lambda _, match=m: self._dlg_predict(match)) if can_edit else None,
            ink=can_edit,
        )

    # ── Dialogs ───────────────────────────────────────────────────────────────

    def _show_setup(self) -> None:
        field = ft.TextField(
            hint_text="Tu nombre en el prode",
            autofocus=True,
            bgcolor=COLORS["bg"],
            color=COLORS["text"],
            border_color=COLORS["primary"],
            focused_border_color=COLORS["primary"],
            text_size=15,
            max_length=20,
        )
        dlg: list = [None]

        async def _ok(_) -> None:
            n = (field.value or "").strip()
            if not n:
                field.error_text = "Ingresá un nombre"
                self._page.update()
                return
            uid = str(uuid.uuid4())[:12]
            await self._page.client_storage.set_async(self._UID, uid)
            await self._page.client_storage.set_async(self._NAME, n)
            if dlg[0]:
                self._page.close(dlg[0])
            try:
                await firebase.save_user(ProdeUser(id=uid, display_name=n))
            except Exception:
                pass
            await self._load()

        dlg[0] = ft.AlertDialog(
            title=ft.Text("¡Bienvenido al Prode! 🎯", size=16,
                         weight=ft.FontWeight.BOLD, color=COLORS["text"]),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("¿Cómo te llamás?", size=13, color=COLORS["text_secondary"]),
                    field,
                    ft.Text("Tu nombre aparece en la tabla del grupo",
                           size=11, color=COLORS["text_secondary"]),
                ], spacing=12, tight=True),
                width=280,
            ),
            bgcolor=COLORS["surface"],
            actions=[
                ft.FilledButton("Empezar", on_click=_ok,
                               style=ft.ButtonStyle(bgcolor=COLORS["primary"])),
            ],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        self._page.open(dlg[0])

    def _dlg_predict(self, m: Match) -> None:
        pred = list(self._preds.get(m.id, (0, 0)))
        ht = ft.Text(str(pred[0]), size=34, weight=ft.FontWeight.BOLD,
                    color=COLORS["text"], width=52, text_align=ft.TextAlign.CENTER)
        at = ft.Text(str(pred[1]), size=34, weight=ft.FontWeight.BOLD,
                    color=COLORS["text"], width=52, text_align=ft.TextAlign.CENTER)
        dlg: list = [None]

        def _btn(icon, side, delta):
            def h(_):
                pred[side] = max(0, pred[side] + delta)
                (ht if side == 0 else at).value = str(pred[side])
                self._page.update()
            return ft.IconButton(icon=icon, icon_color=COLORS["primary"], icon_size=28, on_click=h)

        async def _save(_) -> None:
            self._preds[m.id] = (pred[0], pred[1])
            await self._persist_preds()
            if self._user:
                asyncio.create_task(firebase.save_prediction(Prediction(
                    user_id=self._user.id, match_id=m.id,
                    home_goals=pred[0], away_goals=pred[1],
                )))
            if dlg[0]:
                self._page.close(dlg[0])
            self._render_preds()
            self._render_header()
            self._page.update()

        dlg[0] = ft.AlertDialog(
            title=ft.Text("Pronóstico", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Column([
                            _flag(m.home.name, m.home.id, 44),
                            ft.Text(team_name(m.home.name), size=12, color=COLORS["text"],
                                   weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, expand=True),
                        ft.Column([
                            _flag(m.away.name, m.away.id, 44),
                            ft.Text(team_name(m.away.name), size=12, color=COLORS["text"],
                                   weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, expand=True),
                    ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                    ft.Container(height=6),
                    ft.Row([
                        ft.Column([
                            _btn(ft.Icons.ADD_CIRCLE_OUTLINE, 0, 1),
                            ht,
                            _btn(ft.Icons.REMOVE_CIRCLE_OUTLINE, 0, -1),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, expand=True),
                        ft.Text("–", size=28, color=COLORS["text_secondary"],
                               weight=ft.FontWeight.BOLD),
                        ft.Column([
                            _btn(ft.Icons.ADD_CIRCLE_OUTLINE, 1, 1),
                            at,
                            _btn(ft.Icons.REMOVE_CIRCLE_OUTLINE, 1, -1),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, expand=True),
                    ], alignment=ft.MainAxisAlignment.CENTER,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], spacing=4, tight=True),
                width=300,
            ),
            bgcolor=COLORS["surface"],
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self._page.close(dlg[0]),
                             style=ft.ButtonStyle(color=COLORS["text_secondary"])),
                ft.FilledButton("Guardar", on_click=_save,
                               style=ft.ButtonStyle(bgcolor=COLORS["primary"])),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.open(dlg[0])

    def _dlg_create(self, _=None) -> None:
        field = ft.TextField(
            hint_text="Nombre del grupo (ej: Amigos del trabajo)",
            autofocus=True, bgcolor=COLORS["bg"], color=COLORS["text"],
            border_color=COLORS["primary"], focused_border_color=COLORS["primary"],
            text_size=14, max_length=30,
        )
        dlg: list = [None]

        async def _create(_) -> None:
            n = (field.value or "").strip()
            if not n:
                field.error_text = "Ingresá un nombre"
                self._page.update()
                return
            if not self._user:
                return
            code = _gen_code()
            grp = ProdeGroup(
                code=code, name=n,
                owner_id=self._user.id,
                member_ids=[self._user.id],
                member_names={self._user.id: self._user.display_name},
            )
            self._group = grp
            self._user.group_code = code
            await self._page.client_storage.set_async(self._GROUP, code)
            try:
                await firebase.create_group(grp)
                await firebase.save_user(self._user)
            except Exception:
                pass
            if dlg[0]:
                self._page.close(dlg[0])
            self._render_banner()
            self._render_tabla()
            self._page.update()

        dlg[0] = ft.AlertDialog(
            title=ft.Text("Crear grupo", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
            content=ft.Container(content=ft.Column([field], tight=True), width=280),
            bgcolor=COLORS["surface"],
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self._page.close(dlg[0]),
                             style=ft.ButtonStyle(color=COLORS["text_secondary"])),
                ft.FilledButton("Crear", on_click=_create,
                               style=ft.ButtonStyle(bgcolor=COLORS["primary"])),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.open(dlg[0])

    def _dlg_join(self, _=None) -> None:
        field = ft.TextField(
            hint_text="CÓDIGO DE 6 LETRAS",
            autofocus=True, bgcolor=COLORS["bg"], color=COLORS["text"],
            border_color=COLORS["primary"], focused_border_color=COLORS["primary"],
            text_size=20, max_length=6,
            text_align=ft.TextAlign.CENTER,
            capitalization=ft.TextCapitalization.CHARACTERS,
        )
        err = ft.Text("", size=12, color=COLORS["red"])
        dlg: list = [None]

        async def _join(_) -> None:
            code = (field.value or "").strip().upper()
            if len(code) != 6:
                err.value = "El código debe tener 6 caracteres"
                self._page.update()
                return
            if not self._user:
                return
            try:
                grp = await firebase.join_group(code, self._user.id, self._user.display_name)
                if grp is None:
                    err.value = "Código inválido. Revisá y reintentá."
                    self._page.update()
                    return
                self._group = grp
                self._user.group_code = code
                await self._page.client_storage.set_async(self._GROUP, code)
                await firebase.save_user(self._user)
                if dlg[0]:
                    self._page.close(dlg[0])
                self._render_banner()
                self._render_tabla()
                self._page.update()
                await self._load_leaderboard()
            except Exception:
                err.value = "No se pudo conectar. Verificá el internet."
                self._page.update()

        dlg[0] = ft.AlertDialog(
            title=ft.Text("Unirse a grupo", size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Ingresá el código de invitación:", size=13,
                           color=COLORS["text_secondary"]),
                    field,
                    err,
                ], spacing=10, tight=True),
                width=280,
            ),
            bgcolor=COLORS["surface"],
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self._page.close(dlg[0]),
                             style=ft.ButtonStyle(color=COLORS["text_secondary"])),
                ft.FilledButton("Unirme", on_click=_join,
                               style=ft.ButtonStyle(bgcolor=COLORS["primary"])),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.open(dlg[0])

    def _share(self, _=None) -> None:
        if not self._group:
            return
        store = "https://play.google.com/store/apps/details?id=com.maxfixture.mundial"
        msg = (
            f"🏆 ¡Unite a mi grupo de Prode del Mundial!\n"
            f"Grupo: {self._group.name}\n"
            f"Código: *{self._group.code}*\n\n"
            f"Descargá MaxFixture Mundial 2026:\n{store}"
        )
        self._page.launch_url(f"https://wa.me/?text={urllib.parse.quote(msg)}")

    async def _persist_preds(self) -> None:
        data = {str(k): list(v) for k, v in self._preds.items()}
        await self._page.client_storage.set_async(self._PREDS, json.dumps(data))

    def _on_live_update(self) -> None:
        self._render_preds()
        self._render_header()
        self._page.update()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _section_lbl(text: str) -> ft.Container:
    return ft.Container(
        content=ft.Row([
            ft.Container(width=3, height=14, bgcolor=COLORS["primary"], border_radius=2),
            ft.Text(text, size=11, weight=ft.FontWeight.BOLD, color=COLORS["text_secondary"]),
        ], spacing=8),
        padding=ft.padding.only(left=16, top=16, right=20, bottom=4),
    )
