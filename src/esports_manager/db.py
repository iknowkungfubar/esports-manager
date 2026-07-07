"""SQLite persistence for the eSports Manager."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from esports_manager.models import (
    Availability,
    GameTitle,
    Match,
    MatchFormat,
    MatchResult,
    MatchStatus,
    Player,
    PlayerRole,
    RosterEntry,
    SkillLevel,
    Team,
)


def get_db_path() -> Path:
    """Get the path to the SQLite database."""
    env_path = os.environ.get("ESPORTS_DB_PATH")
    if env_path:
        return Path(env_path)
    home = Path.home() / ".esports-manager"
    home.mkdir(parents=True, exist_ok=True)
    return home / "data.db"


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            name            TEXT NOT NULL,
            gamertag        TEXT PRIMARY KEY,
            email           TEXT NOT NULL DEFAULT '',
            discord         TEXT NOT NULL DEFAULT '',
            game_title      TEXT NOT NULL DEFAULT 'other',
            skill_level     TEXT NOT NULL DEFAULT 'intermediate',
            notes           TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL,
            active          INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS teams (
            name            TEXT PRIMARY KEY,
            game_title      TEXT NOT NULL DEFAULT 'other',
            description     TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL,
            active          INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS roster (
            team_name       TEXT NOT NULL,
            player_name     TEXT NOT NULL,
            gamertag        TEXT NOT NULL,
            role            TEXT NOT NULL DEFAULT 'player',
            joined_at       TEXT NOT NULL,
            PRIMARY KEY (team_name, player_name)
        );

        CREATE TABLE IF NOT EXISTS availability (
            player_name     TEXT NOT NULL,
            day_of_week     INTEGER NOT NULL,
            start_hour      INTEGER NOT NULL,
            end_hour        INTEGER NOT NULL,
            timezone        TEXT NOT NULL DEFAULT 'UTC',
            notes           TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (player_name, day_of_week, start_hour)
        );

        CREATE TABLE IF NOT EXISTS matches (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name       TEXT NOT NULL,
            opponent        TEXT NOT NULL,
            match_date      TEXT NOT NULL,
            match_time      TEXT NOT NULL DEFAULT '',
            format          TEXT NOT NULL DEFAULT 'bo3',
            status          TEXT NOT NULL DEFAULT 'scheduled',
            notes           TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS match_results (
            match_id        INTEGER PRIMARY KEY,
            team_name       TEXT NOT NULL,
            opponent        TEXT NOT NULL,
            team_score      INTEGER NOT NULL DEFAULT 0,
            opponent_score  INTEGER NOT NULL DEFAULT 0,
            winner          TEXT NOT NULL DEFAULT '',
            mvp             TEXT NOT NULL DEFAULT '',
            maps            TEXT NOT NULL DEFAULT '',
            recorded_at     TEXT NOT NULL
        );
    """)
    conn.commit()


def get_connection() -> sqlite3.Connection:
    """Get a database connection with tables ensured."""
    path = get_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    return conn


# ---------------------------------------------------------------------------
# Player CRUD
# ---------------------------------------------------------------------------


def upsert_player(conn: sqlite3.Connection, player: Player) -> None:
    """Insert or update a player."""
    conn.execute(
        """INSERT INTO players (name, gamertag, email, discord, game_title,
           skill_level, notes, created_at, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(gamertag) DO UPDATE SET
               name=excluded.name, email=excluded.email, discord=excluded.discord,
               game_title=excluded.game_title, skill_level=excluded.skill_level,
               notes=excluded.notes, active=excluded.active""",
        (player.name, player.gamertag, player.email, player.discord,
         player.game_title.value, player.skill_level.value,
         player.notes, player.created_at.isoformat(),
         1 if player.active else 0),
    )
    conn.commit()


def get_player(conn: sqlite3.Connection, gamertag: str) -> Player | None:
    """Get a player by gamertag."""
    row = conn.execute(
        "SELECT * FROM players WHERE gamertag = ?", (gamertag,)
    ).fetchone()
    return _row_to_player(row) if row else None


def list_players(
    conn: sqlite3.Connection,
    active_only: bool = True,
    game_title: str | None = None,
) -> list[Player]:
    """List players with optional filters."""
    conditions: list[str] = []
    params: list[Any] = []
    if active_only:
        conditions.append("active = 1")
    if game_title:
        conditions.append("game_title = ?")
        params.append(game_title)
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM players{where} ORDER BY name", params
    ).fetchall()
    return [_row_to_player(r) for r in rows]


def delete_player(conn: sqlite3.Connection, gamertag: str) -> None:
    """Delete a player and their roster entries."""
    conn.execute("DELETE FROM roster WHERE gamertag = ?", (gamertag,))
    conn.execute("DELETE FROM availability WHERE player_name = ?", (gamertag,))
    conn.execute("DELETE FROM players WHERE gamertag = ?", (gamertag,))
    conn.commit()


def _row_to_player(row: sqlite3.Row) -> Player:
    return Player(
        name=row["name"],
        gamertag=row["gamertag"],
        email=row["email"],
        discord=row["discord"],
        game_title=GameTitle(row["game_title"]),
        skill_level=SkillLevel(row["skill_level"]),
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
        active=bool(row["active"]),
    )


# ---------------------------------------------------------------------------
# Team CRUD
# ---------------------------------------------------------------------------


def upsert_team(conn: sqlite3.Connection, team: Team) -> None:
    """Insert or update a team."""
    conn.execute(
        """INSERT INTO teams (name, game_title, description, created_at, active)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
               game_title=excluded.game_title, description=excluded.description,
               active=excluded.active""",
        (team.name, team.game_title.value, team.description,
         team.created_at.isoformat(), 1 if team.active else 0),
    )
    conn.commit()


def get_team(conn: sqlite3.Connection, name: str) -> Team | None:
    """Get a team by name."""
    row = conn.execute("SELECT * FROM teams WHERE name = ?", (name,)).fetchone()
    return _row_to_team(row) if row else None


def list_teams(conn: sqlite3.Connection, active_only: bool = True) -> list[Team]:
    """List all teams."""
    query = "SELECT * FROM teams"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY name"
    return [_row_to_team(r) for r in conn.execute(query).fetchall()]


def delete_team(conn: sqlite3.Connection, name: str) -> None:
    """Delete a team and its roster."""
    conn.execute("DELETE FROM roster WHERE team_name = ?", (name,))
    conn.execute("DELETE FROM teams WHERE name = ?", (name,))
    conn.commit()


def _row_to_team(row: sqlite3.Row) -> Team:
    return Team(
        name=row["name"],
        game_title=GameTitle(row["game_title"]),
        description=row["description"],
        created_at=datetime.fromisoformat(row["created_at"]),
        active=bool(row["active"]),
    )


# ---------------------------------------------------------------------------
# Roster CRUD
# ---------------------------------------------------------------------------


def add_roster_entry(conn: sqlite3.Connection, entry: RosterEntry) -> None:
    """Add a player to a team roster."""
    conn.execute(
        """INSERT OR REPLACE INTO roster (team_name, player_name, gamertag, role, joined_at)
           VALUES (?, ?, ?, ?, ?)""",
        (entry.team_name, entry.player_name, entry.gamertag,
         entry.role.value, entry.joined_at.isoformat()),
    )
    conn.commit()


def remove_roster_entry(conn: sqlite3.Connection, team_name: str, gamertag: str) -> None:
    """Remove a player from a team roster."""
    conn.execute(
        "DELETE FROM roster WHERE team_name = ? AND gamertag = ?",
        (team_name, gamertag),
    )
    conn.commit()


def list_roster(conn: sqlite3.Connection, team_name: str) -> list[RosterEntry]:
    """List all roster entries for a team."""
    rows = conn.execute(
        "SELECT * FROM roster WHERE team_name = ? ORDER BY role, player_name",
        (team_name,),
    ).fetchall()
    return [_row_to_roster(r) for r in rows]


def list_player_teams(conn: sqlite3.Connection, gamertag: str) -> list[dict[str, Any]]:
    """List teams a player belongs to."""
    rows = conn.execute(
        """SELECT r.*, t.game_title as team_game, t.description
           FROM roster r JOIN teams t ON r.team_name = t.name
           WHERE r.gamertag = ? ORDER BY t.name""",
        (gamertag,),
    ).fetchall()
    return [dict(r) for r in rows]


def _row_to_roster(row: sqlite3.Row) -> RosterEntry:
    return RosterEntry(
        team_name=row["team_name"],
        player_name=row["player_name"],
        gamertag=row["gamertag"],
        role=PlayerRole(row["role"]),
        joined_at=datetime.fromisoformat(row["joined_at"]),
    )


# ---------------------------------------------------------------------------
# Availability CRUD
# ---------------------------------------------------------------------------


def upsert_availability(conn: sqlite3.Connection, avail: Availability) -> None:
    """Set a player's availability slot."""
    conn.execute(
        """INSERT OR REPLACE INTO availability
           (player_name, day_of_week, start_hour, end_hour, timezone, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (avail.player_name, avail.day_of_week, avail.start_hour,
         avail.end_hour, avail.timezone, avail.notes),
    )
    conn.commit()


def remove_availability(
    conn: sqlite3.Connection, player_name: str, day_of_week: int, start_hour: int,
) -> None:
    """Remove an availability slot."""
    conn.execute(
        "DELETE FROM availability WHERE player_name=? AND day_of_week=? AND start_hour=?",
        (player_name, day_of_week, start_hour),
    )
    conn.commit()


def get_player_availability(
    conn: sqlite3.Connection, player_name: str,
) -> list[Availability]:
    """Get all availability slots for a player."""
    rows = conn.execute(
        "SELECT * FROM availability WHERE player_name = ? ORDER BY day_of_week, start_hour",
        (player_name,),
    ).fetchall()
    return [_row_to_avail(r) for r in rows]


def get_team_availability(
    conn: sqlite3.Connection, team_name: str,
) -> dict[str, list[Availability]]:
    """Get availability for all players on a team, grouped by player."""
    rows = conn.execute(
        """SELECT a.* FROM availability a
           JOIN roster r ON a.player_name = r.gamertag
           WHERE r.team_name = ?
           ORDER BY a.player_name, a.day_of_week""",
        (team_name,),
    ).fetchall()
    result: dict[str, list[Availability]] = {}
    for r in rows:
        avail = _row_to_avail(r)
        if avail.player_name not in result:
            result[avail.player_name] = []
        result[avail.player_name].append(avail)
    return result


def get_overlapping_availability(
    conn: sqlite3.Connection, team_name: str,
) -> list[dict[str, Any]]:
    """Find time slots where multiple team members are available."""
    rows = conn.execute(
        """SELECT a.day_of_week, a.start_hour, a.end_hour, COUNT(*) as player_count,
                  GROUP_CONCAT(a.player_name) as players
           FROM availability a
           JOIN roster r ON a.player_name = r.gamertag
           WHERE r.team_name = ?
           GROUP BY a.day_of_week, a.start_hour
           HAVING player_count > 1
           ORDER BY player_count DESC, a.day_of_week, a.start_hour""",
        (team_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def _row_to_avail(row: sqlite3.Row) -> Availability:
    return Availability(
        player_name=row["player_name"],
        day_of_week=row["day_of_week"],
        start_hour=row["start_hour"],
        end_hour=row["end_hour"],
        timezone=row["timezone"],
        notes=row["notes"],
    )


# ---------------------------------------------------------------------------
# Match CRUD
# ---------------------------------------------------------------------------


def create_match(conn: sqlite3.Connection, match: Match) -> int:
    """Create a new match, returns the match ID."""
    cursor = conn.execute(
        """INSERT INTO matches (team_name, opponent, match_date, match_time, format, status, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (match.team_name, match.opponent, match.match_date, match.match_time,
         match.format.value, match.status.value, match.notes, match.created_at.isoformat()),
    )
    conn.commit()
    return cursor.lastrowid


def get_match(conn: sqlite3.Connection, match_id: int) -> Match | None:
    """Get a match by ID."""
    row = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    return _row_to_match(row) if row else None


def list_matches(
    conn: sqlite3.Connection,
    team_name: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[Match]:
    """List matches with optional filters."""
    conditions: list[str] = []
    params: list[Any] = []

    if team_name:
        conditions.append("team_name = ?")
        params.append(team_name)
    if status:
        conditions.append("status = ?")
        params.append(status)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM matches{where} ORDER BY match_date DESC, match_time DESC LIMIT ?",
        [*params, limit],
    ).fetchall()
    return [_row_to_match(r) for r in rows]


def update_match_status(conn: sqlite3.Connection, match_id: int, status: str) -> None:
    """Update a match's status."""
    conn.execute("UPDATE matches SET status = ? WHERE id = ?", (status, match_id))
    conn.commit()


def delete_match(conn: sqlite3.Connection, match_id: int) -> None:
    """Delete a match and its result."""
    conn.execute("DELETE FROM match_results WHERE match_id = ?", (match_id,))
    conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    conn.commit()


def record_match_result(conn: sqlite3.Connection, result: MatchResult) -> None:
    """Record a match result."""
    conn.execute(
        """INSERT OR REPLACE INTO match_results
           (match_id, team_name, opponent, team_score, opponent_score, winner, mvp, maps, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (result.match_id, result.team_name, result.opponent,
         result.team_score, result.opponent_score, result.winner,
         result.mvp, result.maps, result.recorded_at.isoformat()),
    )
    # Also mark the match as completed
    update_match_status(conn, result.match_id, "completed")
    conn.commit()


def get_match_result(conn: sqlite3.Connection, match_id: int) -> MatchResult | None:
    """Get the result of a match."""
    row = conn.execute(
        "SELECT * FROM match_results WHERE match_id = ?", (match_id,)
    ).fetchone()
    return _row_to_result(row) if row else None


def get_team_record(conn: sqlite3.Connection, team_name: str) -> dict[str, Any]:
    """Get W/L/T record and win rate for a team."""
    rows = conn.execute(
        "SELECT winner, COUNT(*) as cnt FROM match_results WHERE team_name = ? GROUP BY winner",
        (team_name,),
    ).fetchall()
    wins = 0
    losses = 0
    draws = 0
    for r in rows:
        if r["winner"] == "team":
            wins = r["cnt"]
        elif r["winner"] == "opponent":
            losses = r["cnt"]
        elif r["winner"] == "draw":
            draws = r["cnt"]
    total = wins + losses + draws
    win_rate = round(wins / total * 100, 1) if total > 0 else 0.0
    return {"wins": wins, "losses": losses, "draws": draws, "total": total, "win_rate": win_rate}


def _row_to_match(row: sqlite3.Row) -> Match:
    return Match(
        id=row["id"],
        team_name=row["team_name"],
        opponent=row["opponent"],
        match_date=row["match_date"],
        match_time=row["match_time"],
        format=MatchFormat(row["format"]) if hasattr(MatchFormat, row["format"].upper().replace("-", "_")) else MatchFormat.BO3,
        status=MatchStatus(row["status"]) if hasattr(MatchStatus, row["status"].upper()) else MatchStatus.SCHEDULED,
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_result(row: sqlite3.Row) -> MatchResult:
    return MatchResult(
        match_id=row["match_id"],
        team_name=row["team_name"],
        opponent=row["opponent"],
        team_score=row["team_score"],
        opponent_score=row["opponent_score"],
        winner=row["winner"],
        mvp=row["mvp"],
        maps=row["maps"],
        recorded_at=datetime.fromisoformat(row["recorded_at"]),
    )
