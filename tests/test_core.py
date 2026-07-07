"""Tests for eSports Manager."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from esports_manager.models import (
    Availability,
    GameTitle,
    Player,
    PlayerRole,
    RosterEntry,
    SkillLevel,
    Team,
)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestModels:
    def test_player_defaults(self):
        p = Player(name="Test", gamertag="test#1234")
        assert p.game_title == GameTitle.OTHER
        assert p.skill_level == SkillLevel.INTERMEDIATE
        assert p.active is True

    def test_availability_valid(self):
        a = Availability(player_name="p1", day_of_week=0, start_hour=18, end_hour=21)
        assert a.day_of_week == 0
        assert a.start_hour == 18

    def test_availability_invalid_day(self):
        with pytest.raises(ValueError):
            Availability(player_name="p1", day_of_week=7, start_hour=18, end_hour=21)

    def test_availability_invalid_hour(self):
        with pytest.raises(ValueError):
            Availability(player_name="p1", day_of_week=0, start_hour=25, end_hour=26)

    def test_availability_start_after_end(self):
        with pytest.raises(ValueError):
            Availability(player_name="p1", day_of_week=0, start_hour=21, end_hour=18)

    def test_team_defaults(self):
        t = Team(name="Test Team")
        assert t.game_title == GameTitle.OTHER
        assert t.active is True

    def test_roster_entry(self):
        r = RosterEntry(team_name="T1", player_name="Alice", gamertag="alice#1234", role=PlayerRole.CAPTAIN)
        assert r.role == PlayerRole.CAPTAIN


# ---------------------------------------------------------------------------
# DB tests
# ---------------------------------------------------------------------------


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    """Create a temporary database for testing."""
    from esports_manager.db import _ensure_tables
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    return conn


class TestPlayerCRUD:
    def test_create_and_get_player(self, conn):
        from esports_manager.db import get_player, upsert_player
        p = Player(name="Alice", gamertag="alice#1234", game_title=GameTitle.VALORANT, skill_level=SkillLevel.SEMI_PRO)
        upsert_player(conn, p)
        got = get_player(conn, "alice#1234")
        assert got is not None
        assert got.name == "Alice"
        assert got.game_title == GameTitle.VALORANT

    def test_update_player(self, conn):
        from esports_manager.db import get_player, upsert_player
        upsert_player(conn, Player(name="Bob", gamertag="bob#5678"))
        upsert_player(conn, Player(name="Robert", gamertag="bob#5678", skill_level=SkillLevel.ADVANCED))
        got = get_player(conn, "bob#5678")
        assert got.name == "Robert"
        assert got.skill_level == SkillLevel.ADVANCED

    def test_list_players(self, conn):
        from esports_manager.db import list_players, upsert_player
        upsert_player(conn, Player(name="A", gamertag="a#1"))
        upsert_player(conn, Player(name="B", gamertag="b#2"))
        players = list_players(conn)
        assert len(players) == 2

    def test_delete_player(self, conn):
        from esports_manager.db import delete_player, get_player, upsert_player
        upsert_player(conn, Player(name="Del", gamertag="del#0"))
        delete_player(conn, "del#0")
        assert get_player(conn, "del#0") is None

    def test_list_players_filter_game(self, conn):
        from esports_manager.db import list_players, upsert_player
        upsert_player(conn, Player(name="A", gamertag="a#1", game_title=GameTitle.VALORANT))
        upsert_player(conn, Player(name="B", gamertag="b#2", game_title=GameTitle.CS2))
        players = list_players(conn, game_title="valorant")
        assert len(players) == 1


class TestTeamCRUD:
    def test_create_and_get_team(self, conn):
        from esports_manager.db import get_team, upsert_team
        t = Team(name="Valorants", game_title=GameTitle.VALORANT)
        upsert_team(conn, t)
        got = get_team(conn, "Valorants")
        assert got is not None
        assert got.game_title == GameTitle.VALORANT

    def test_list_teams(self, conn):
        from esports_manager.db import list_teams, upsert_team
        upsert_team(conn, Team(name="T1"))
        upsert_team(conn, Team(name="T2"))
        assert len(list_teams(conn)) == 2

    def test_delete_team(self, conn):
        from esports_manager.db import delete_team, get_team, upsert_team
        upsert_team(conn, Team(name="Temp"))
        delete_team(conn, "Temp")
        assert get_team(conn, "Temp") is None


class TestRosterCRUD:
    def test_add_and_list_roster(self, conn):
        from esports_manager.db import add_roster_entry, list_roster, upsert_player, upsert_team
        upsert_player(conn, Player(name="Alice", gamertag="alice#1"))
        upsert_team(conn, Team(name="Team A"))
        add_roster_entry(conn, RosterEntry(team_name="Team A", player_name="Alice", gamertag="alice#1"))
        roster = list_roster(conn, "Team A")
        assert len(roster) == 1
        assert roster[0].player_name == "Alice"

    def test_remove_roster_entry(self, conn):
        from esports_manager.db import add_roster_entry, list_roster, remove_roster_entry, upsert_player, upsert_team
        upsert_player(conn, Player(name="Bob", gamertag="bob#2"))
        upsert_team(conn, Team(name="Team B"))
        add_roster_entry(conn, RosterEntry(team_name="Team B", player_name="Bob", gamertag="bob#2"))
        remove_roster_entry(conn, "Team B", "bob#2")
        assert len(list_roster(conn, "Team B")) == 0

    def test_roster_roles(self, conn):
        from esports_manager.db import add_roster_entry, list_roster, upsert_player, upsert_team
        upsert_player(conn, Player(name="Cap", gamertag="cap#1"))
        upsert_team(conn, Team(name="T"))
        add_roster_entry(conn, RosterEntry(team_name="T", player_name="Cap", gamertag="cap#1", role=PlayerRole.CAPTAIN))
        assert list_roster(conn, "T")[0].role == PlayerRole.CAPTAIN


class TestAvailabilityCRUD:
    def test_set_and_get_availability(self, conn):
        from esports_manager.db import get_player_availability, upsert_availability
        a = Availability(player_name="alice#1", day_of_week=0, start_hour=18, end_hour=21)
        upsert_availability(conn, a)
        slots = get_player_availability(conn, "alice#1")
        assert len(slots) == 1
        assert slots[0].start_hour == 18

    def test_get_team_availability(self, conn):
        from esports_manager.db import (
            add_roster_entry,
            get_team_availability,
            upsert_availability,
            upsert_player,
            upsert_team,
        )
        upsert_player(conn, Player(name="A", gamertag="a#1"))
        upsert_player(conn, Player(name="B", gamertag="b#2"))
        upsert_team(conn, Team(name="T"))
        add_roster_entry(conn, RosterEntry(team_name="T", player_name="A", gamertag="a#1"))
        add_roster_entry(conn, RosterEntry(team_name="T", player_name="B", gamertag="b#2"))
        upsert_availability(conn, Availability(player_name="a#1", day_of_week=0, start_hour=18, end_hour=21))
        upsert_availability(conn, Availability(player_name="b#2", day_of_week=0, start_hour=18, end_hour=21))
        avail = get_team_availability(conn, "T")
        assert len(avail) == 2

    def test_overlapping_availability(self, conn):
        from esports_manager.db import (
            add_roster_entry,
            get_overlapping_availability,
            upsert_availability,
            upsert_player,
            upsert_team,
        )
        upsert_player(conn, Player(name="A", gamertag="a#1"))
        upsert_player(conn, Player(name="B", gamertag="b#2"))
        upsert_team(conn, Team(name="T"))
        add_roster_entry(conn, RosterEntry(team_name="T", player_name="A", gamertag="a#1"))
        add_roster_entry(conn, RosterEntry(team_name="T", player_name="B", gamertag="b#2"))
        upsert_availability(conn, Availability(player_name="a#1", day_of_week=0, start_hour=18, end_hour=21))
        upsert_availability(conn, Availability(player_name="b#2", day_of_week=0, start_hour=18, end_hour=21))
        overlaps = get_overlapping_availability(conn, "T")
        assert len(overlaps) >= 1
        assert overlaps[0]["player_count"] >= 2

    def test_remove_availability(self, conn):
        from esports_manager.db import (
            get_player_availability,
            remove_availability,
            upsert_availability,
        )
        a = Availability(player_name="p1", day_of_week=1, start_hour=14, end_hour=16)
        upsert_availability(conn, a)
        remove_availability(conn, "p1", 1, 14)
        assert len(get_player_availability(conn, "p1")) == 0


# ---------------------------------------------------------------------------
# Dashboard API tests
# ---------------------------------------------------------------------------


class TestDashboardAPI:
    @pytest.fixture
    def client(self, tmp_path):
        """Create test client with seeded data."""
        import os
        from esports_manager.db import (
            _ensure_tables,
            add_roster_entry,
            upsert_player,
            upsert_team,
        )
        # Override the database path
        os.environ["ESPORTS_DB_PATH"] = str(tmp_path / "test.db")
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        _ensure_tables(conn)

        from esports_manager.models import Player, RosterEntry, Team
        upsert_player(conn, Player(name="Alice", gamertag="alice#1", game_title=GameTitle.VALORANT))
        upsert_team(conn, Team(name="Valorants", game_title=GameTitle.VALORANT))
        add_roster_entry(conn, RosterEntry(team_name="Valorants", player_name="Alice", gamertag="alice#1"))
        conn.close()

        from esports_manager.dashboard import create_app
        from fastapi.testclient import TestClient

        # Monkeypatch the DB path
        import esports_manager.db as db_module
        original_path = db_module.get_db_path
        db_module.get_db_path = lambda: db_path

        app = create_app()
        yield TestClient(app)
        db_module.get_db_path = original_path

    def test_teams_endpoint(self, client):
        res = client.get("/api/teams")
        assert res.status_code == 200
        data = res.json()
        assert len(data["teams"]) >= 1
        assert data["teams"][0]["roster_count"] >= 1

    def test_team_detail(self, client):
        res = client.get("/api/teams/Valorants")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Valorants"
        assert len(data["roster"]) >= 1

    def test_players_endpoint(self, client):
        res = client.get("/api/players")
        assert res.status_code == 200
        data = res.json()
        assert len(data["players"]) >= 1

    def test_dashboard_page(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "eSports Manager" in res.text

    def test_team_page(self, client):
        res = client.get("/teams/Valorants")
        assert res.status_code == 200
        assert "Roster" in res.text


# ---------------------------------------------------------------------------
# CLI parser tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_player_create_parser(self):
        from esports_manager.cli import _build_parser
        p = _build_parser()
        args = p.parse_args(["player", "create", "Alice", "--gamertag", "alice#1", "--game", "valorant"])
        assert args.command == "player"
        assert args.player_command == "create"
        assert args.name == "Alice"
        assert args.gamertag == "alice#1"

    def test_team_create_parser(self):
        from esports_manager.cli import _build_parser
        p = _build_parser()
        args = p.parse_args(["team", "create", "TeamA", "--game", "cs2"])
        assert args.command == "team"
        assert args.team_command == "create"

    def test_roster_parser(self):
        from esports_manager.cli import _build_parser
        p = _build_parser()
        args = p.parse_args(["team", "roster", "TeamA"])
        assert args.command == "team"
        assert args.team_command == "roster"
        assert args.name == "TeamA"

    def test_availability_set_parser(self):
        from esports_manager.cli import _build_parser
        p = _build_parser()
        args = p.parse_args(["availability", "set", "--player", "p1", "--day", "0", "--start", "18", "--end", "21"])
        assert args.command == "availability"
        assert args.avail_command == "set"

    def test_availability_show_parser(self):
        from esports_manager.cli import _build_parser
        p = _build_parser()
        args = p.parse_args(["availability", "show", "--player", "p1"])
        assert args.command == "availability"
        assert args.avail_command == "show"

    def test_dashboard_parser(self):
        from esports_manager.cli import _build_parser
        p = _build_parser()
        args = p.parse_args(["dashboard", "--port", "9000"])
        assert args.command == "dashboard"
        assert args.port == 9000
