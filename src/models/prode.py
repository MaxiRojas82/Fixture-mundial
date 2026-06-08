from dataclasses import dataclass, field


@dataclass
class ProdeUser:
    id: str
    display_name: str
    group_code: str = ""


@dataclass
class Prediction:
    user_id: str
    match_id: int
    home_goals: int
    away_goals: int


@dataclass
class ProdeGroup:
    code: str
    name: str
    owner_id: str
    member_ids: list[str] = field(default_factory=list)
    member_names: dict[str, str] = field(default_factory=dict)


@dataclass
class LeaderboardEntry:
    user_id: str
    display_name: str
    points: int = 0
    exact: int = 0
    correct: int = 0


def calc_points(pred_home: int, pred_away: int, actual_home: int, actual_away: int) -> int:
    if (pred_home, pred_away) == (actual_home, actual_away):
        return 3
    pred_res = "H" if pred_home > pred_away else ("A" if pred_away > pred_home else "D")
    actual_res = "H" if actual_home > actual_away else ("A" if actual_away > actual_home else "D")
    return 2 if pred_res == actual_res else 0
