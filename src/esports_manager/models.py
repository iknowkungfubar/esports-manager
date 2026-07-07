"""Data models for the eSports Manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class PlayerRole(str, Enum):
    """Role a player can have on a team roster."""

    CAPTAIN = "captain"
    COACH = "coach"
    PLAYER = "player"
    SUBSTITUTE = "substitute"
    MANAGER = "manager"


class GameTitle(str, Enum):
    """Supported game titles."""

    VALORANT = "valorant"
    LEAGUE_OF_LEGENDS = "league-of-legends"
    CS2 = "cs2"
    DOTA2 = "dota2"
    OVERWATCH2 = "overwatch2"
    APEX_LEGENDS = "apex-legends"
    FORTNITE = "fortnite"
    ROCKET_LEAGUE = "rocket-league"
    STREET_FIGHTER6 = "street-fighter-6"
    TEKKEN8 = "tekken-8"
    SMASH_BROS = "smash-bros"
    OTHER = "other"


class SkillLevel(str, Enum):
    """Player skill/rank level."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    SEMI_PRO = "semi-pro"
    PROFESSIONAL = "professional"


@dataclass
class Player:
    """A player in the eSports system."""

    name: str  # Display name / real name
    gamertag: str  # In-game handle (unique)
    email: str = ""
    discord: str = ""
    game_title: GameTitle = GameTitle.OTHER
    skill_level: SkillLevel = SkillLevel.INTERMEDIATE
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    active: bool = True


@dataclass
class Team:
    """A team or club within the system."""

    name: str  # Team name (unique)
    game_title: GameTitle = GameTitle.OTHER
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    active: bool = True


@dataclass
class RosterEntry:
    """A player's membership on a team."""

    team_name: str
    player_name: str
    gamertag: str  # Denormalized for quick display
    role: PlayerRole = PlayerRole.PLAYER
    joined_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Availability:
    """A player's availability for a specific day/time slot."""

    player_name: str
    day_of_week: int  # 0=Monday, 6=Sunday
    start_hour: int  # 0-23
    end_hour: int  # 0-23
    timezone: str = "UTC"
    notes: str = ""

    def __post_init__(self) -> None:
        """Validate time ranges."""
        if not 0 <= self.day_of_week <= 6:
            raise ValueError("day_of_week must be 0-6")
        if not 0 <= self.start_hour <= 23:
            raise ValueError("start_hour must be 0-23")
        if not 0 <= self.end_hour <= 23:
            raise ValueError("end_hour must be 0-23")
        if self.start_hour >= self.end_hour:
            raise ValueError("start_hour must be before end_hour")


class MatchStatus(str, Enum):
    """Status of a scheduled match."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


class MatchFormat(str, Enum):
    """Format/type of match."""

    BO1 = "bo1"
    BO3 = "bo3"
    BO5 = "bo5"
    SCRIM = "scrim"
    TOURNAMENT = "tournament"
    LEAGUE = "league"


@dataclass
class Match:
    """A scheduled match or scrim."""

    id: int | None = None
    team_name: str = ""
    opponent: str = ""
    match_date: str = ""  # ISO date string
    match_time: str = ""  # HH:MM
    format: MatchFormat = MatchFormat.BO3
    status: MatchStatus = MatchStatus.SCHEDULED
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MatchResult:
    """Result of a completed match."""

    match_id: int
    team_name: str
    opponent: str
    team_score: int = 0
    opponent_score: int = 0
    winner: str = ""  # "team" or "opponent" or "draw"
    mvp: str = ""  # Gamertag of MVP
    maps: str = ""  # JSON string of map results
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def team_won(self) -> bool:
        return self.winner == "team"

    def is_draw(self) -> bool:
        return self.winner == "draw"
