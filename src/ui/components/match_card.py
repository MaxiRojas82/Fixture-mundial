import flet as ft
from src.models.match import Match, MatchStatus
from src.ui.theme import COLORS
from src.ui.flags import get_flag_url, get_flag_b64
from src.ui.translations import team_name, round_name, is_knockout


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


def build_match_card(match: Match, on_tap=None, show_date: bool = False) -> ft.Container:
    is_live = match.is_live

    if is_live:
        status_label = f"🔴  {match.elapsed}'"
        status_color = COLORS["live"]
        card_border = ft.border.all(1.5, COLORS["live"] + "77")
        score_color = COLORS["live"]
    elif match.status == MatchStatus.FINISHED:
        status_label = "FT"
        status_color = COLORS["text_secondary"]
        card_border = ft.border.all(1, COLORS["card_border"])
        score_color = COLORS["text"]
    elif match.status == MatchStatus.HALFTIME:
        status_label = "HT"
        status_color = COLORS["yellow"]
        card_border = ft.border.all(1, COLORS["yellow"] + "55")
        score_color = COLORS["yellow"]
    else:
        local_dt = match.date.astimezone()
        if show_date:
            _MONTHS = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
            status_label = f"{local_dt.day} {_MONTHS[local_dt.month - 1]} · {local_dt.strftime('%H:%M')}"
        else:
            status_label = local_dt.strftime("%H:%M")
        status_color = COLORS["text_secondary"]
        card_border = ft.border.all(1, COLORS["card_border"])
        score_color = COLORS["text_secondary"]

    card_shadow = ft.BoxShadow(
        blur_radius=12,
        spread_radius=0,
        color=COLORS["shadow"],
        offset=ft.Offset(0, 3),
    )

    body_rows: list[ft.Control] = [
        ft.Row([
            ft.Text(round_name(match.group) if is_knockout(match.group) else match.group,
                    size=11, color=COLORS["text_secondary"]),
            ft.Container(
                content=ft.Text(
                    status_label,
                    size=11,
                    color=status_color,
                    weight=ft.FontWeight.BOLD,
                ),
                padding=ft.padding.symmetric(horizontal=8, vertical=2),
                border_radius=10,
                bgcolor=status_color + "22" if is_live else "transparent",
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Row([
            # Equipo local
            ft.Row([
                _flag_img(match.home.name),
                ft.Text(
                    team_name(match.home.name),
                    size=13,
                    weight=ft.FontWeight.W_500,
                    color=COLORS["text"],
                    no_wrap=False,
                    expand=True,
                ),
            ], spacing=8, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            # Marcador
            ft.Container(
                content=ft.Text(
                    "vs" if match.score.home is None and match.score.away is None else match.score_display,
                    size=17,
                    weight=ft.FontWeight.BOLD,
                    color=score_color,
                ),
                padding=ft.padding.symmetric(horizontal=8),
            ),
            # Equipo visitante
            ft.Row([
                ft.Text(
                    team_name(match.away.name),
                    size=13,
                    weight=ft.FontWeight.W_500,
                    color=COLORS["text"],
                    text_align=ft.TextAlign.RIGHT,
                    no_wrap=False,
                    expand=True,
                ),
                _flag_img(match.away.name),
            ], spacing=8, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
               alignment=ft.MainAxisAlignment.END),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
    ]

    if match.venue:
        body_rows.append(
            ft.Row([
                ft.Icon(ft.Icons.LOCATION_ON_OUTLINED, size=12, color=COLORS["text_secondary"]),
                ft.Text(match.venue, size=11, color=COLORS["text_secondary"], expand=True, no_wrap=True),
            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        )

    return ft.Container(
        content=ft.Column(body_rows, spacing=8),
        padding=ft.padding.all(16),
        margin=ft.margin.symmetric(horizontal=16, vertical=5),
        bgcolor=COLORS["card"],
        border_radius=14,
        border=card_border,
        shadow=card_shadow,
        on_click=on_tap,
        ink=True,
    )
