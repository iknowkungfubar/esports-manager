# Copyright (c) 2024-2025 iknowkungfubar
# Licensed under the MIT License. See LICENSE file for details.

"""Tests for eSports Manager."""

from __future__ import annotations

import os
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

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
        with pytest.raises(ValueError, match="day_of_week must be 0-6"):
            Availability(player_name="p1", day_of_week=7, start_hour=18, end_hour=21)

    def test_availability_invalid_hour(self):
        with pytest.raises(ValueError, match="start_hour must be 0-23"):
            Availability(player_name="p1", day_of_week=0, start_hour=25, end_hour=26)

    def test_availability_start_after_end(self):
        with pytest.raises(ValueError, match="start_hour must be before end_hour"):
            Availability(player_name="p1", day_of_week=0, start_hour=21, end_hour=18)

    def test_team_defaults(self):
        t = Team(name="Test Team")
        assert t.game_title == GameTitle.OTHER
        assert t.active is True

    def test_roster_entry(self):
        r = RosterEntry(
            team_name="T1",
            player_name="Alice",
            gamertag="alice#1234",
            role=PlayerRole.CAPTAIN,
        )
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

        p = Player(
            name="Alice",
            gamertag="alice#1234",
            game_title=GameTitle.VALORANT,
            skill_level=SkillLevel.SEMI_PRO,
        )
        upsert_player(conn, p)
        got = get_player(conn, "alice#1234")
        assert got is not None
        assert got.name == "Alice"
        assert got.game_title == GameTitle.VALORANT

    def test_update_player(self, conn):
        from esports_manager.db import get_player, upsert_player

        upsert_player(conn, Player(name="Bob", gamertag="bob#5678"))
        upsert_player(
            conn,
            Player(name="Robert", gamertag="bob#5678", skill_level=SkillLevel.ADVANCED),
        )
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
        add_roster_entry(
            conn,
            RosterEntry(team_name="Team A", player_name="Alice", gamertag="alice#1"),
        )
        roster = list_roster(conn, "Team A")
        assert len(roster) == 1
        assert roster[0].player_name == "Alice"

    def test_remove_roster_entry(self, conn):
        from esports_manager.db import (
            add_roster_entry,
            list_roster,
            remove_roster_entry,
            upsert_player,
            upsert_team,
        )

        upsert_player(conn, Player(name="Bob", gamertag="bob#2"))
        upsert_team(conn, Team(name="Team B"))
        add_roster_entry(conn, RosterEntry(team_name="Team B", player_name="Bob", gamertag="bob#2"))
        remove_roster_entry(conn, "Team B", "bob#2")
        assert len(list_roster(conn, "Team B")) == 0

    def test_roster_roles(self, conn):
        from esports_manager.db import add_roster_entry, list_roster, upsert_player, upsert_team

        upsert_player(conn, Player(name="Cap", gamertag="cap#1"))
        upsert_team(conn, Team(name="T"))
        add_roster_entry(
            conn,
            RosterEntry(
                team_name="T",
                player_name="Cap",
                gamertag="cap#1",
                role=PlayerRole.CAPTAIN,
            ),
        )
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
        upsert_availability(
            conn,
            Availability(player_name="a#1", day_of_week=0, start_hour=18, end_hour=21),
        )
        upsert_availability(
            conn,
            Availability(player_name="b#2", day_of_week=0, start_hour=18, end_hour=21),
        )
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
        upsert_availability(
            conn,
            Availability(player_name="a#1", day_of_week=0, start_hour=18, end_hour=21),
        )
        upsert_availability(
            conn,
            Availability(player_name="b#2", day_of_week=0, start_hour=18, end_hour=21),
        )
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
        add_roster_entry(
            conn,
            RosterEntry(team_name="Valorants", player_name="Alice", gamertag="alice#1"),
        )
        conn.close()

        from fastapi.testclient import TestClient

        # Monkeypatch the DB path
        import esports_manager.db as db_module
        from esports_manager.dashboard import create_app

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
        args = p.parse_args(
            ["player", "create", "Alice", "--gamertag", "alice#1", "--game", "valorant"],
        )
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
        args = p.parse_args(
            ["availability", "set", "--player", "p1", "--day", "0", "--start", "18", "--end", "21"],
        )
        assert args.command == "availability"
        assert args.avail_command == "set"
        assert args.player == "p1"

    def test_availability_show_parser(self):
        from esports_manager.cli import _build_parser

        p = _build_parser()
        args = p.parse_args(["availability", "show", "--player", "p1"])
        assert args.command == "availability"
        assert args.avail_command == "show"
        assert args.player == "p1"

    def test_dashboard_parser(self):
        from esports_manager.cli import _build_parser

        p = _build_parser()
        args = p.parse_args(["dashboard", "--port", "9000"])
        assert args.command == "dashboard"
        assert args.port == 9000


# ---------------------------------------------------------------------------
# Match tests
# ---------------------------------------------------------------------------


class TestMatchModel:
    def test_match_defaults(self):
        m = Match(team_name="T1", opponent="T2", match_date="2026-07-10")
        assert m.format == MatchFormat.BO3
        assert m.status == MatchStatus.SCHEDULED

    def test_match_result_win(self):
        r = MatchResult(
            match_id=1,
            team_name="T1",
            opponent="T2",
            team_score=3,
            opponent_score=1,
            winner="team",
        )
        assert r.team_won() is True
        assert r.is_draw() is False

    def test_match_result_draw(self):
        r = MatchResult(
            match_id=2,
            team_name="T1",
            opponent="T2",
            team_score=2,
            opponent_score=2,
            winner="draw",
        )
        assert r.team_won() is False
        assert r.is_draw() is True


class TestMatchCRUD:
    def test_create_and_get_match(self, conn):
        from esports_manager.db import create_match, get_match

        m = Match(team_name="T1", opponent="T2", match_date="2026-07-10")
        mid = create_match(conn, m)
        assert mid > 0
        got = get_match(conn, mid)
        assert got is not None
        assert got.opponent == "T2"

    def test_list_matches_by_team(self, conn):
        from esports_manager.db import create_match, list_matches

        create_match(conn, Match(team_name="T1", opponent="A", match_date="2026-07-10"))
        create_match(conn, Match(team_name="T2", opponent="B", match_date="2026-07-11"))
        t1_matches = list_matches(conn, team_name="T1")
        assert len(t1_matches) == 1

    def test_record_result(self, conn):
        from esports_manager.db import (
            create_match,
            get_match,
            get_match_result,
            record_match_result,
        )

        mid = create_match(conn, Match(team_name="T1", opponent="T2", match_date="2026-07-10"))
        result = MatchResult(
            match_id=mid,
            team_name="T1",
            opponent="T2",
            team_score=3,
            opponent_score=1,
            winner="team",
        )
        record_match_result(conn, result)

        match = get_match(conn, mid)
        assert match.status == MatchStatus.COMPLETED

        stored = get_match_result(conn, mid)
        assert stored is not None
        assert stored.winner == "team"

    def test_team_record(self, conn):
        from esports_manager.db import create_match, get_team_record, record_match_result

        mid1 = create_match(conn, Match(team_name="T1", opponent="A", match_date="2026-07-10"))
        mid2 = create_match(conn, Match(team_name="T1", opponent="B", match_date="2026-07-11"))
        record_match_result(
            conn,
            MatchResult(
                match_id=mid1,
                team_name="T1",
                opponent="A",
                team_score=3,
                opponent_score=0,
                winner="team",
            ),
        )
        record_match_result(
            conn,
            MatchResult(
                match_id=mid2,
                team_name="T1",
                opponent="B",
                team_score=1,
                opponent_score=3,
                winner="opponent",
            ),
        )

        rec = get_team_record(conn, "T1")
        assert rec["wins"] == 1
        assert rec["losses"] == 1
        assert rec["total"] == 2
        assert rec["win_rate"] == 50.0

    def test_delete_match_cascades(self, conn):
        from esports_manager.db import create_match, delete_match, get_match

        mid = create_match(conn, Match(team_name="T1", opponent="T2", match_date="2026-07-10"))
        delete_match(conn, mid)
        assert get_match(conn, mid) is None

    def test_match_cli_parser(self):
        from esports_manager.cli import _build_parser

        p = _build_parser()
        args = p.parse_args(["match", "create", "T1", "--opponent", "T2", "--date", "2026-07-10"])
        assert args.command == "match"
        assert args.match_command == "create"
        assert args.team == "T1"
        assert args.opponent == "T2"
        assert args.date == "2026-07-10"

    def test_record_cli_parser(self):
        from esports_manager.cli import _build_parser

        p = _build_parser()
        args = p.parse_args(["record", "T1"])
        assert args.command == "record"
        assert args.team == "T1"


# ---------------------------------------------------------------------------
# Bracket engine tests
# ---------------------------------------------------------------------------


class TestBracketEngine:
    def test_generate_4_team_bracket(self):
        from esports_manager.bracket import generate_bracket

        teams = ["TeamA", "TeamB", "TeamC", "TeamD"]
        bracket = generate_bracket(teams)
        assert len(bracket) >= 3  # 2 semis + 1 final
        rounds = {s["round"] for s in bracket}
        assert 0 in rounds  # First round exists

    def test_generate_8_team_bracket(self):
        from esports_manager.bracket import generate_bracket

        teams = [f"Team{i}" for i in range(8)]
        bracket = generate_bracket(teams)
        assert len(bracket) >= 7  # 4 quarters + 2 semis + 1 final

    def test_generate_3_team_with_bye(self):
        from esports_manager.bracket import generate_bracket

        bracket = generate_bracket(["T1", "T2", "T3"])
        # 3 teams -> padded to 4, first round has 2 matches
        first_round = [s for s in bracket if s["round"] == 0]
        assert len(first_round) == 2

    def test_advance_winner(self):
        from esports_manager.bracket import advance_winner, generate_bracket

        bracket = generate_bracket(["T1", "T2", "T3", "T4"])
        # T1 beats T2 in round 0 position 0
        bracket = advance_winner(bracket, 0, 0, "team1")
        # T1 should advance to round 1 position 0 as team1
        round1 = [s for s in bracket if s["round"] == 1 and s["position"] == 0]
        assert len(round1) > 0
        assert round1[0]["team1"] == "T1"

    def test_advance_winner_position_1(self):
        from esports_manager.bracket import advance_winner, generate_bracket

        bracket = generate_bracket(["T1", "T2", "T3", "T4"])
        bracket = advance_winner(bracket, 0, 1, "team2")
        round1 = [s for s in bracket if s["round"] == 1 and s["position"] == 0]
        assert len(round1) > 0
        # Seeded order: T1 vs T4 (pos 0), T2 vs T3 (pos 1). team2 of pos 1 = T3
        assert round1[0]["team2"] == "T3"

    def test_complete_bracket_to_winner(self):
        from esports_manager.bracket import (
            advance_winner,
            generate_bracket,
            get_tournament_winner,
            is_bracket_complete,
        )

        bracket = generate_bracket(["T1", "T2", "T3", "T4"])
        bracket = advance_winner(bracket, 0, 0, "team1")  # T1 wins
        bracket = advance_winner(bracket, 0, 1, "team2")  # T4 wins
        bracket = advance_winner(bracket, 1, 0, "team1")  # T1 wins final
        assert is_bracket_complete(bracket)
        assert get_tournament_winner(bracket) == "T1"

    def test_get_winner_none_if_incomplete(self):
        from esports_manager.bracket import get_tournament_winner

        assert get_tournament_winner([]) is None

    def test_generate_less_than_2_teams(self):
        from esports_manager.bracket import generate_bracket

        assert generate_bracket(["Only"]) == []
        assert generate_bracket([]) == []

    def test_tournament_model_defaults(self):
        from esports_manager.models import Tournament, TournamentStatus

        t = Tournament(name="Test Cup", game_title="valorant")
        assert t.status == TournamentStatus.UPCOMING
        assert t.max_teams == 8


# ---------------------------------------------------------------------------
# Tournament CRUD tests
# ---------------------------------------------------------------------------


class TestTournamentCRUD:
    def test_create_tournament(self, conn):
        from esports_manager.db import create_tournament, get_tournament
        from esports_manager.models import Tournament

        t = Tournament(name="Summer Cup", game_title="valorant")
        tid = create_tournament(conn, t)
        assert tid > 0
        got = get_tournament(conn, tid)
        assert got is not None
        assert got.name == "Summer Cup"

    def test_list_tournaments(self, conn):
        from esports_manager.db import create_tournament, list_tournaments
        from esports_manager.models import Tournament

        create_tournament(conn, Tournament(name="Cup1", game_title="cs2"))
        create_tournament(conn, Tournament(name="Cup2", game_title="valorant"))
        assert len(list_tournaments(conn)) >= 2

    def test_register_team(self, conn):
        from esports_manager.db import (
            create_tournament,
            list_tournament_teams,
            register_tournament_team,
        )
        from esports_manager.models import Tournament, TournamentTeam

        tid = create_tournament(conn, Tournament(name="Test", game_title="valorant"))
        register_tournament_team(conn, TournamentTeam(tournament_id=tid, team_name="TeamA", seed=1))
        teams = list_tournament_teams(conn, tid)
        assert len(teams) == 1
        assert teams[0].team_name == "TeamA"

    def test_unregister_team(self, conn):
        from esports_manager.db import (
            create_tournament,
            list_tournament_teams,
            register_tournament_team,
            unregister_tournament_team,
        )
        from esports_manager.models import Tournament, TournamentTeam

        tid = create_tournament(conn, Tournament(name="Test", game_title="valorant"))
        register_tournament_team(conn, TournamentTeam(tournament_id=tid, team_name="TeamA"))
        unregister_tournament_team(conn, tid, "TeamA")
        assert len(list_tournament_teams(conn, tid)) == 0

    def test_tournament_cli_parser(self):
        from esports_manager.cli import _build_parser

        p = _build_parser()
        args = p.parse_args(["tournament", "create", "SummerCup", "--game", "valorant"])
        assert args.command == "tournament"
        assert args.tournament_command == "create"
        assert args.name == "SummerCup"
