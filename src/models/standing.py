from dataclasses import dataclass


@dataclass
class TeamStanding:
    rank: int
    team_id: int
    team_name: str
    team_logo: str
    group: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
