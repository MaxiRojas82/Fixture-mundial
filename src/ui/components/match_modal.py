"""Modal de vista rápida de partido — se abre al tocar una tarjeta."""

import flet as ft
from src.models.match import Match, MatchStatus
from src.ui.theme import COLORS
from src.ui.flags import get_flag_url, get_flag_b64
from src.ui.translations import team_name, round_name, is_knockout

_DAYS   = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MONTHS = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
           "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _flag(name: str, size: int = 56) -> ft.Control:
    h = round(size * 0.67)
    b64 = get_flag_b64(name)
    if b64:
        return ft.Image(src_base64=b64, width=size, height=h,
                       fit=ft.ImageFit.CONTAIN, border_radius=4)
    url = get_flag_url(name, 80)
    if url:
        return ft.Image(src=url, width=size, height=h,
                       fit=ft.ImageFit.CONTAIN, border_radius=4)
    return ft.Container(
        content=ft.Text("?", size=18, color=COLORS["text_secondary"]),
        width=size, height=h,
        bgcolor=COLORS["card_border"], border_radius=4,
        alignment=ft.alignment.center,
    )


def _status_chip(m: Match) -> ft.Control:
    """Badge superior: «● 1er tiempo · ~10'», «Entretiempo», «Finalizado», «Programado»."""
    if m.status == MatchStatus.HALFTIME:
        text, color = "Entretiempo", COLORS["yellow"]
    elif m.status == MatchStatus.PENALTY:
        text, color = "Penales", COLORS["live"]
    elif m.status == MatchStatus.EXTRA_TIME:
        mins = m.display_minute
        text = f"Alargue · ~{mins}'" if mins else "Alargue"
        color = COLORS["live"]
    elif m.is_live:
        mins = m.display_minute
        half = "1er tiempo" if (mins or 0) <= 50 else "2do tiempo"
        text = f"{half} · ~{mins}'" if mins else "En vivo"
        color = COLORS["live"]
    elif m.status == MatchStatus.FINISHED:
        text, color = "Finalizado", COLORS["text_secondary"]
    else:
        text, color = "Programado", COLORS["text_secondary"]

    inner: list[ft.Control] = []
    if m.is_live:
        inner.append(ft.Container(width=7, height=7, bgcolor=color, border_radius=4))
    inner.append(ft.Text(text, size=12, color=color, weight=ft.FontWeight.BOLD))

    return ft.Container(
        content=ft.Row(inner, spacing=6, tight=True,
                      vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=color + "1F",
        border=ft.border.all(1, color + "55"),
        border_radius=14,
        padding=ft.padding.symmetric(horizontal=14, vertical=5),
    )


def _stage_label(m: Match) -> str:
    if is_knockout(m.group):
        return round_name(m.group)
    if m.group:
        return f"Fase de grupos · {m.group.replace('Group', 'Grupo')}"
    return ""


def _info_row(icon, text: str) -> ft.Row:
    return ft.Row([
        ft.Icon(icon, size=15, color=COLORS["text_secondary"]),
        ft.Text(text, size=12.5, color=COLORS["text_secondary"],
               expand=True, no_wrap=False),
    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def open_match_modal(page: ft.Page, m: Match) -> None:
    local_dt = m.date.astimezone()
    fecha = (f"{_DAYS[local_dt.weekday()]} {local_dt.day} "
             f"{_MONTHS[local_dt.month]}, {local_dt.strftime('%H:%M')}")

    # Centro: marcador si hay, sino «VS»
    if m.score.home is not None and m.score.away is not None:
        center_color = COLORS["live"] if m.is_live else COLORS["text"]
        center = ft.Text(f"{m.score.home} – {m.score.away}", size=26,
                        weight=ft.FontWeight.BOLD, color=center_color)
    else:
        center = ft.Text("VS", size=18, weight=ft.FontWeight.BOLD,
                        color=COLORS["text_secondary"])

    def _team_col(name: str) -> ft.Column:
        return ft.Column([
            _flag(name),
            ft.Text(team_name(name), size=13, weight=ft.FontWeight.W_600,
                   color=COLORS["text"], text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, expand=True)

    stage = _stage_label(m)

    body_items: list[ft.Control] = [
        ft.Row([_status_chip(m)], alignment=ft.MainAxisAlignment.CENTER),
    ]
    if stage:
        body_items.append(ft.Text(stage, size=12, color=COLORS["text_secondary"],
                                  text_align=ft.TextAlign.CENTER))
    body_items += [
        ft.Container(height=6),
        ft.Row([
            _team_col(m.home.name),
            center,
            _team_col(m.away.name),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.SPACE_AROUND),
        ft.Container(height=4),
        ft.Divider(color=COLORS["card_border"], height=1),
        ft.Container(height=2),
    ]
    if m.venue:
        body_items.append(_info_row(ft.Icons.STADIUM, m.venue))
    body_items.append(_info_row(ft.Icons.ACCESS_TIME, fecha))

    dlg = ft.AlertDialog(
        content=ft.Container(
            content=ft.Column(body_items, spacing=8, tight=True,
                             horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=310,
        ),
        bgcolor=COLORS["surface"],
        shape=ft.RoundedRectangleBorder(radius=18),
        actions=[
            ft.TextButton("Cerrar", on_click=lambda _: page.close(dlg),
                         style=ft.ButtonStyle(color=COLORS["text_secondary"])),
            ft.FilledButton(
                "Ver detalle",
                on_click=lambda _: (page.close(dlg), page.go(f"/match/{m.id}")),
                style=ft.ButtonStyle(bgcolor=COLORS["primary"]),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.open(dlg)
