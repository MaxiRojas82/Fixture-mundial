import flet as ft
from src.models.match import Match, MatchStatus
from src.ui.theme import COLORS
from src.ui.flags import get_flag_url, get_flag_b64
from src.ui.translations import team_name


def _flag_img(team_name: str, size: int = 28) -> ft.Control:
    h = int(size * 0.67)
    b64 = get_flag_b64(team_name)
    if b64:
        return ft.Image(src_base64=b64, width=size, height=h,
                       fit=ft.ImageFit.CONTAIN, border_radius=3)
    url = get_flag_url(team_name, 40)
    if url:
        return ft.Image(src=url, width=size, height=h,
                       fit=ft.ImageFit.CONTAIN, border_radius=3)
    return ft.Container(width=size, height=h)


def _dot_label(text: str, color: str) -> ft.Row:
    return ft.Row([
        ft.Container(width=7, height=7, bgcolor=color, border_radius=4),
        ft.Text(text, size=11.5, color=color, weight=ft.FontWeight.BOLD),
    ], spacing=6, tight=True, alignment=ft.MainAxisAlignment.CENTER,
       vertical_alignment=ft.CrossAxisAlignment.CENTER)


def build_match_card(match: Match, on_tap=None, show_date: bool = False,
                     featured: bool = False) -> ft.Container:
    is_live = match.is_live
    local_dt = match.date.astimezone()
    has_score = match.score.home is not None and match.score.away is not None

    # ── Estado superior (centrado) + texto central ────────────────────────
    if match.status == MatchStatus.HALFTIME:
        status_widget: ft.Control = _dot_label("ENTRETIEMPO", COLORS["yellow"])
        center_text, center_color = match.score_display, COLORS["yellow"]
        card_border = ft.border.all(1, COLORS["yellow"] + "55")
    elif is_live:
        mins = match.display_minute
        lbl = "EN VIVO" + (f"  ·  ~{mins}'" if mins else "")
        status_widget = _dot_label(lbl, COLORS["live"])
        if has_score:
            center_text, center_color = match.score_display, COLORS["live"]
        else:
            center_text, center_color = "En juego", COLORS["text_secondary"]
        card_border = ft.border.all(1.5, COLORS["live"] + "77")
    elif match.status == MatchStatus.FINISHED:
        status_widget = ft.Text("FINALIZADO", size=11, weight=ft.FontWeight.BOLD,
                               color=COLORS["text_secondary"],
                               text_align=ft.TextAlign.CENTER)
        center_text, center_color = match.score_display, COLORS["text"]
        card_border = ft.border.all(1, COLORS["card_border"])
    else:
        status_widget = ft.Text(
            f"{local_dt.strftime('%d/%m')}  {local_dt.strftime('%H:%M')}",
            size=11.5, weight=ft.FontWeight.W_600,
            color=COLORS["text_secondary"], text_align=ft.TextAlign.CENTER,
        )
        center_text, center_color = "vs", COLORS["text_secondary"]
        card_border = ft.border.all(1, COLORS["card_border"])

    if featured:
        card_border = ft.border.all(1.5, COLORS["yellow"] + "AA")

    body_rows: list[ft.Control] = []

    if featured:
        body_rows.append(ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Text("⭐", size=11),
                    ft.Text("Partido del día", size=11, color=COLORS["yellow"],
                           weight=ft.FontWeight.BOLD),
                ], spacing=5, tight=True),
                bgcolor=COLORS["yellow"] + "1A",
                border=ft.border.all(1, COLORS["yellow"] + "55"),
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=12, vertical=3),
            ),
        ], alignment=ft.MainAxisAlignment.CENTER))

    body_rows.append(ft.Row([status_widget], alignment=ft.MainAxisAlignment.CENTER))

    body_rows.append(ft.Row([
        # Equipo local: nombre + bandera
        ft.Row([
            ft.Text(
                team_name(match.home.name),
                size=13.5, weight=ft.FontWeight.W_600, color=COLORS["text"],
                text_align=ft.TextAlign.RIGHT, no_wrap=False, expand=True,
            ),
            _flag_img(match.home.name, 26),
        ], spacing=8, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
           alignment=ft.MainAxisAlignment.END),
        # Centro: marcador / «En juego» / «vs»
        ft.Container(
            content=ft.Text(
                center_text,
                size=16 if has_score else 12,
                weight=ft.FontWeight.BOLD if has_score else ft.FontWeight.W_500,
                color=center_color,
                italic=center_text == "En juego",
            ),
            padding=ft.padding.symmetric(horizontal=10),
        ),
        # Equipo visitante: bandera + nombre
        ft.Row([
            _flag_img(match.away.name, 26),
            ft.Text(
                team_name(match.away.name),
                size=13.5, weight=ft.FontWeight.W_600, color=COLORS["text"],
                no_wrap=False, expand=True,
            ),
        ], spacing=8, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER))

    if match.venue:
        body_rows.append(ft.Text(
            match.venue, size=11, color=COLORS["text_secondary"],
            text_align=ft.TextAlign.CENTER, no_wrap=True,
        ))

    return ft.Container(
        content=ft.Column(body_rows, spacing=9,
                         horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        padding=ft.padding.all(14),
        margin=ft.margin.symmetric(horizontal=16, vertical=5),
        bgcolor=COLORS["card"],
        border_radius=14,
        border=card_border,
        shadow=ft.BoxShadow(
            blur_radius=12,
            spread_radius=0,
            color=COLORS["shadow"],
            offset=ft.Offset(0, 3),
        ),
        on_click=on_tap,
        ink=True,
    )
