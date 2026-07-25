# Copyright (c) 2024-2025 iknowkungfubar
# Licensed under the MIT License. See LICENSE file for details.

"""Command-line interface for eSports Manager."""

from __future__ import annotations

import argparse
import sys
from itertools import groupby

from rich.console import Console
from rich.table import Table

from esports_manager.bracket import (
    advance_winner,
    generate_bracket,
    get_tournament_winner,
    is_bracket_complete,
)
from esports_manager.db import (
    add_roster_entry,
    create_match,
    create_tournament,
    delete_match,
    delete_player,
    get_connection,
    get_match,
    get_overlapping_availability,
    get_player,
    get_player_availability,
    get_team,
    get_team_availability,
    get_team_record,
    get_tournament,
    list_matches,
    list_players,
    list_roster,
    list_teams,
    list_tournament_teams,
    list_tournaments,
    load_bracket_slots,
    record_match_result,
    register_tournament_team,
    remove_roster_entry,
    save_bracket_slots,
    unregister_tournament_team,
    update_tournament_status,
    upsert_availability,
    upsert_player,
    upsert_team,
)
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
    Tournament,
    TournamentTeam,
)

console = Console()

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _build_parser() -> argparse.ArgumentParser:  # noqa: PLR0915
    parser = argparse.ArgumentParser(
        prog="esports",
        description="eSports Manager — team/club management platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Player commands
    p_player = sub.add_parser("player", help="Player management")
    p_player_sub = p_player.add_subparsers(dest="player_command", required=True)

    pc = p_player_sub.add_parser("create", help="Create a player")
    pc.add_argument("name", help="Display name")
    pc.add_argument("--gamertag", required=True, help="In-game handle (unique)")
    pc.add_argument("--email", default="")
    pc.add_argument("--discord", default="")
    pc.add_argument(
        "--game",
        choices=[g.value for g in GameTitle],
        default=GameTitle.OTHER.value,
    )
    pc.add_argument(
        "--skill",
        choices=[s.value for s in SkillLevel],
        default=SkillLevel.INTERMEDIATE.value,
    )
    pc.add_argument("--notes", default="")

    pl = p_player_sub.add_parser("list", help="List players")
    pl.add_argument("--game", choices=[g.value for g in GameTitle], help="Filter by game")
    pl.add_argument("--inactive", action="store_true", help="Include inactive players")

    pd = p_player_sub.add_parser("delete", help="Delete a player")
    pd.add_argument("gamertag", help="Gamertag to delete")

    # Team commands
    p_team = sub.add_parser("team", help="Team management")
    p_team_sub = p_team.add_subparsers(dest="team_command", required=True)

    tc = p_team_sub.add_parser("create", help="Create a team")
    tc.add_argument("name", help="Team name (unique)")
    tc.add_argument(
        "--game",
        choices=[g.value for g in GameTitle],
        default=GameTitle.OTHER.value,
    )
    tc.add_argument("--description", default="")

    tl = p_team_sub.add_parser("list", help="List teams")
    tl.add_argument("--inactive", action="store_true", help="Include inactive teams")

    ta = p_team_sub.add_parser("add-player", help="Add player to team roster")
    ta.add_argument("team", help="Team name")
    ta.add_argument("player", help="Player name")
    ta.add_argument("--gamertag", required=True)
    ta.add_argument(
        "--role",
        choices=[r.value for r in PlayerRole],
        default=PlayerRole.PLAYER.value,
    )

    tr = p_team_sub.add_parser("remove-player", help="Remove player from team")
    tr.add_argument("team", help="Team name")
    tr.add_argument("gamertag", help="Player gamertag")

    tro = p_team_sub.add_parser("roster", help="Show team roster with availability")
    tro.add_argument("name", help="Team name")

    # Availability commands
    p_avail = sub.add_parser("availability", help="Player availability")
    p_avail_sub = p_avail.add_subparsers(dest="avail_command", required=True)

    aset = p_avail_sub.add_parser("set", help="Set availability for a player")
    aset.add_argument("--player", required=True, help="Player gamertag")
    aset.add_argument("--day", type=int, required=True, choices=range(7), help="0=Mon..6=Sun")
    aset.add_argument("--start", type=int, required=True, choices=range(24), help="Start hour 0-23")
    aset.add_argument("--end", type=int, required=True, choices=range(24), help="End hour 0-23")

    ash = p_avail_sub.add_parser("show", help="Show player availability")
    ash.add_argument("--player", required=True, help="Player gamertag")

    at = p_avail_sub.add_parser("team", help="Show team availability overview")
    at.add_argument("team", help="Team name")

    # Dashboard
    p_dash = sub.add_parser("dashboard", help="Start web dashboard")
    p_dash.add_argument("--host", default="127.0.0.1")
    p_dash.add_argument("--port", type=int, default=8555)

    # Match commands
    p_match = sub.add_parser("match", help="Match/scrimmage management")
    p_match_sub = p_match.add_subparsers(dest="match_command", required=True)

    mc = p_match_sub.add_parser("create", help="Schedule a match")
    mc.add_argument("team", help="Team name")
    mc.add_argument("--opponent", required=True, help="Opponent name")
    mc.add_argument("--date", required=True, help="Match date (YYYY-MM-DD)")
    mc.add_argument("--time", default="", help="Match time (HH:MM)")
    mc.add_argument(
        "--format",
        choices=[f.value for f in MatchFormat],
        default=MatchFormat.BO3.value,
    )
    mc.add_argument("--notes", default="")

    ml = p_match_sub.add_parser("list", help="List matches")
    ml.add_argument("--team", help="Filter by team")
    ml.add_argument(
        "--status",
        choices=[s.value for s in MatchStatus],
        help="Filter by status",
    )

    mr = p_match_sub.add_parser("record", help="Record match result")
    mr.add_argument("match_id", type=int, help="Match ID")
    mr.add_argument("team_score", type=int)
    mr.add_argument("opponent_score", type=int)
    mr.add_argument("--mvp", default="", help="MVP gamertag")
    mr.add_argument("--maps", default="", help="Map results as JSON string")

    md = p_match_sub.add_parser("delete", help="Delete a match")
    md.add_argument("match_id", type=int)

    # Record command
    pr = sub.add_parser("record", help="Show team W/L/T record")
    pr.add_argument("team", help="Team name")

    # Tournament commands
    p_tourney = sub.add_parser("tournament", help="Tournament management")
    p_tourney_sub = p_tourney.add_subparsers(dest="tournament_command", required=True)

    tcr = p_tourney_sub.add_parser("create", help="Create a tournament")
    tcr.add_argument("name", help="Tournament name")
    tcr.add_argument(
        "--game",
        choices=[g.value for g in GameTitle],
        default=GameTitle.OTHER.value,
    )
    tcr.add_argument("--max-teams", type=int, default=8)

    _ = p_tourney_sub.add_parser("list", help="List tournaments")

    treg = p_tourney_sub.add_parser("register-team", help="Register team for tournament")
    treg.add_argument("tournament_id", type=int)
    treg.add_argument("team", help="Team name")
    treg.add_argument("--seed", type=int, default=0)

    tdrop = p_tourney_sub.add_parser("drop-team", help="Drop team from tournament")
    tdrop.add_argument("tournament_id", type=int)
    tdrop.add_argument("team", help="Team name")

    tstart = p_tourney_sub.add_parser("start", help="Start tournament (generate bracket)")
    tstart.add_argument("tournament_id", type=int)

    tb = p_tourney_sub.add_parser("bracket", help="Show tournament bracket")
    tb.add_argument("tournament_id", type=int)

    trec = p_tourney_sub.add_parser("record-result", help="Record bracket match result")
    trec.add_argument("tournament_id", type=int)
    trec.add_argument("round", type=int, help="Round number (0 = first round)")
    trec.add_argument("position", type=int, help="Position in round")
    trec.add_argument("winner", choices=["team1", "team2"])
    trec.add_argument("--score", default="", help="Score string (e.g. '3-1')")

    return parser


# ---------------------------------------------------------------------------
# Player commands
# ---------------------------------------------------------------------------


def cmd_player_create(args: argparse.Namespace) -> None:
    player = Player(
        name=args.name,
        gamertag=args.gamertag,
        email=args.email,
        discord=args.discord,
        game_title=GameTitle(args.game),
        skill_level=SkillLevel(args.skill),
        notes=args.notes,
    )
    conn = get_connection()
    upsert_player(conn, player)
    conn.close()
    console.print(
        f"[green]✓[/green] Player [bold]{args.name}[/bold] ({args.gamertag}) created",
    )


def cmd_player_list(args: argparse.Namespace) -> None:
    conn = get_connection()
    players = list_players(
        conn,
        active_only=not args.inactive,
        game_title=args.game,
    )
    conn.close()

    if not players:
        console.print("[yellow]No players found.[/yellow]")
        return

    table = Table(title="Players")
    table.add_column("Name", style="bold")
    table.add_column("Gamertag", style="cyan")
    table.add_column("Game")
    table.add_column("Skill")
    table.add_column("Discord")
    table.add_column("Active")

    for p in players:
        table.add_row(
            p.name,
            p.gamertag,
            p.game_title.value,
            p.skill_level.value,
            p.discord or "-",
            "Yes" if p.active else "No",
        )
    console.print(table)


def cmd_player_delete(args: argparse.Namespace) -> None:
    conn = get_connection()
    player = get_player(conn, args.gamertag)
    if player is None:
        conn.close()
        console.print(f"[red]✗[/red] Player '{args.gamertag}' not found")
        return
    delete_player(conn, args.gamertag)
    conn.close()
    console.print(f"[green]✓[/green] Player [bold]{args.gamertag}[/bold] deleted")


# ---------------------------------------------------------------------------
# Team commands
# ---------------------------------------------------------------------------


def cmd_team_create(args: argparse.Namespace) -> None:
    team = Team(
        name=args.name,
        game_title=GameTitle(args.game),
        description=args.description,
    )
    conn = get_connection()
    upsert_team(conn, team)
    conn.close()
    console.print(f"[green]✓[/green] Team [bold]{args.name}[/bold] created")


def cmd_team_list(args: argparse.Namespace) -> None:
    conn = get_connection()
    teams = list_teams(conn, active_only=not args.inactive)
    conn.close()

    if not teams:
        console.print("[yellow]No teams found.[/yellow]")
        return

    table = Table(title="Teams")
    table.add_column("Name", style="bold")
    table.add_column("Game")
    table.add_column("Description")
    table.add_column("Active")

    for t in teams:
        table.add_row(t.name, t.game_title.value, t.description or "-", "Yes" if t.active else "No")
    console.print(table)


def cmd_team_add_player(args: argparse.Namespace) -> None:
    conn = get_connection()
    player = get_player(conn, args.gamertag)
    if player is None:
        conn.close()
        console.print(f"[red]✗[/red] Player '{args.gamertag}' not found")
        return
    team = get_team(conn, args.team)
    if team is None:
        conn.close()
        console.print(f"[red]✗[/red] Team '{args.team}' not found")
        return

    entry = RosterEntry(
        team_name=args.team,
        player_name=player.name,
        gamertag=args.gamertag,
        role=PlayerRole(args.role),
    )
    add_roster_entry(conn, entry)
    conn.close()
    console.print(
        f"[green]✓[/green] [bold]{args.gamertag}[/bold] added to "
        f"[bold]{args.team}[/bold] as {args.role}",
    )


def cmd_team_remove_player(args: argparse.Namespace) -> None:
    conn = get_connection()
    remove_roster_entry(conn, args.team, args.gamertag)
    conn.close()
    console.print(
        f"[green]✓[/green] [bold]{args.gamertag}[/bold] removed from [bold]{args.team}[/bold]",
    )


def cmd_team_roster(args: argparse.Namespace) -> None:
    conn = get_connection()
    team = get_team(conn, args.name)
    if team is None:
        conn.close()
        console.print(f"[red]✗[/red] Team '{args.name}' not found")
        return

    roster = list_roster(conn, args.name)
    avail = get_team_availability(conn, args.name)
    overlaps = get_overlapping_availability(conn, args.name)
    conn.close()

    console.print(f"[bold]Team:[/bold] {team.name} ({team.game_title.value})")
    console.print(f"Description: {team.description}")
    console.print("")

    if not roster:
        console.print("[yellow]No players on this team.[/yellow]")
        return

    table = Table(title=f"Roster ({len(roster)} players)")
    table.add_column("Role", style="bold")
    table.add_column("Player")
    table.add_column("Gamertag", style="cyan")
    table.add_column("Available", justify="right")

    for r in roster:
        player_avail = avail.get(r.gamertag, [])
        avail_count = len(player_avail)
        table.add_row(r.role.value, r.player_name, r.gamertag, str(avail_count))
    console.print(table)

    if overlaps:
        console.print("\n[bold]Best Practice Times:[/bold]")
        for o in overlaps[:5]:
            console.print(
                f"  {DAY_NAMES[o['day_of_week']]} "
                f"{o['start_hour']:02d}:00-{o['end_hour']:02d}:00 "
                f"— {o['player_count']} player(s)",
            )


# ---------------------------------------------------------------------------
# Availability commands
# ---------------------------------------------------------------------------


def cmd_avail_set(args: argparse.Namespace) -> None:
    try:
        avail = Availability(
            player_name=args.player,
            day_of_week=args.day,
            start_hour=args.start,
            end_hour=args.end,
        )
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        return

    conn = get_connection()
    upsert_availability(conn, avail)
    conn.close()
    console.print(
        f"[green]✓[/green] Availability set for [bold]{args.player}[/bold] "
        f"on {DAY_NAMES[args.day]} {args.start:02d}:00-{args.end:02d}:00",
    )


def cmd_avail_show(args: argparse.Namespace) -> None:
    conn = get_connection()
    slots = get_player_availability(conn, args.player)
    conn.close()

    if not slots:
        console.print(f"[yellow]No availability set for '{args.player}'.[/yellow]")
        return

    table = Table(title=f"Availability — {args.player}")
    table.add_column("Day")
    table.add_column("Hours")

    for s in slots:
        table.add_row(DAY_NAMES[s.day_of_week], f"{s.start_hour:02d}:00-{s.end_hour:02d}:00")
    console.print(table)


def cmd_avail_team(args: argparse.Namespace) -> None:
    conn = get_connection()
    overlaps = get_overlapping_availability(conn, args.team)
    avail = get_team_availability(conn, args.team)
    conn.close()

    if not avail:
        console.print(f"[yellow]No availability data for team '{args.team}'.[/yellow]")
        return

    console.print(f"[bold]Availability Overview — {args.team}[/bold]")
    console.print("")

    for player_name, slots in sorted(avail.items()):
        times = [
            f"{DAY_NAMES[s.day_of_week]} {s.start_hour:02d}:00-{s.end_hour:02d}:00" for s in slots
        ]
        console.print(f"  [cyan]{player_name}[/cyan]: {', '.join(times)}")

    if overlaps:
        console.print("\n[bold]Overlapping Slots:[/bold]")
        for o in overlaps[:5]:
            console.print(
                f"  {DAY_NAMES[o['day_of_week']]} {o['start_hour']:02d}:00-"
                f"{o['end_hour']:02d}:00 — {o['player_count']} players",
            )


# ---------------------------------------------------------------------------
# Match commands
# ---------------------------------------------------------------------------


def _cmd_match_create(args: argparse.Namespace) -> None:
    format_enum = MatchFormat(args.format)
    match = Match(
        team_name=args.team,
        opponent=args.opponent,
        match_date=args.date,
        match_time=args.time,
        format=format_enum,
        notes=args.notes,
    )
    conn = get_connection()
    match_id = create_match(conn, match)
    conn.close()
    console.print(
        f"[green]✓[/green] Match #{match_id} scheduled — [bold]{args.team}[/bold] "
        f"vs {args.opponent} on {args.date}",
    )


def _cmd_match_list(args: argparse.Namespace) -> None:
    conn = get_connection()
    matches = list_matches(conn, team_name=args.team, status=args.status)
    conn.close()

    if not matches:
        console.print("[yellow]No matches found.[/yellow]")
        return

    table = Table(title=f"Matches ({len(matches)})")
    table.add_column("ID", justify="right")
    table.add_column("Date")
    table.add_column("Team")
    table.add_column("Opponent")
    table.add_column("Format")
    table.add_column("Status")

    for m in matches:
        table.add_row(
            str(m.id),
            m.match_date,
            m.team_name,
            m.opponent,
            m.format.value,
            m.status.value,
        )
    console.print(table)


def _cmd_match_record(args: argparse.Namespace) -> None:
    conn = get_connection()
    match = get_match(conn, args.match_id)
    if match is None:
        conn.close()
        console.print(f"[red]✗[/red] Match #{args.match_id} not found")
        return

    winner = (
        "team"
        if args.team_score > args.opponent_score
        else "opponent"
        if args.opponent_score > args.team_score
        else "draw"
    )
    result = MatchResult(
        match_id=args.match_id,
        team_name=match.team_name,
        opponent=match.opponent,
        team_score=args.team_score,
        opponent_score=args.opponent_score,
        winner=winner,
        mvp=args.mvp,
        maps=args.maps,
    )
    record_match_result(conn, result)
    conn.close()

    status_text = (
        "[green]WON[/green]"
        if winner == "team"
        else "[red]LOST[/red]"
        if winner == "opponent"
        else "[yellow]DRAW[/yellow]"
    )
    console.print(
        f"[green]✓[/green] Result recorded: {status_text} {args.team_score}-{args.opponent_score}",
    )


def _cmd_match_delete(args: argparse.Namespace) -> None:
    conn = get_connection()
    delete_match(conn, args.match_id)
    conn.close()
    console.print(f"[green]✓[/green] Match #{args.match_id} deleted")


def _cmd_record(args: argparse.Namespace) -> None:
    conn = get_connection()
    rec = get_team_record(conn, args.team)
    conn.close()

    console.print(f"[bold]Record: {args.team}[/bold]")
    console.print(f"  {rec['wins']}W / {rec['losses']}L / {rec['draws']}D")
    console.print(f"  Win Rate: [bold]{rec['win_rate']}%[/bold]")
    console.print(f"  Total: {rec['total']} match(es)")


# ---------------------------------------------------------------------------
# Tournament commands
# ---------------------------------------------------------------------------


def _cmd_tournament(args: argparse.Namespace) -> None:  # noqa: C901, PLR0912, PLR0915
    if args.tournament_command == "create":
        t = Tournament(
            name=args.name,
            game_title=args.game,
            max_teams=args.max_teams,
        )
        conn = get_connection()
        tid = create_tournament(conn, t)
        conn.close()
        console.print(f"[green]✓[/green] Tournament [bold]{args.name}[/bold] created (ID: {tid})")

    elif args.tournament_command == "list":
        conn = get_connection()
        tournaments = list_tournaments(conn)
        conn.close()
        if not tournaments:
            console.print("[yellow]No tournaments created yet.[/yellow]")
            return
        table = Table(title="Tournaments")
        table.add_column("ID", justify="right")
        table.add_column("Name", style="cyan")
        table.add_column("Game")
        table.add_column("Status")
        table.add_column("Teams", justify="right")
        for t in tournaments:
            conn2 = get_connection()
            teams = list_tournament_teams(conn2, t.id)
            conn2.close()
            table.add_row(str(t.id), t.name, t.game_title, t.status.value, str(len(teams)))
        console.print(table)

    elif args.tournament_command == "register-team":
        conn = get_connection()
        register_tournament_team(
            conn,
            TournamentTeam(
                tournament_id=args.tournament_id,
                team_name=args.team,
                seed=args.seed,
            ),
        )
        conn.close()
        console.print(
            f"[green]✓[/green] [bold]{args.team}[/bold] registered for "
            f"tournament #{args.tournament_id}",
        )

    elif args.tournament_command == "drop-team":
        conn = get_connection()
        unregister_tournament_team(conn, args.tournament_id, args.team)
        conn.close()
        console.print(
            f"[green]✓[/green] [bold]{args.team}[/bold] dropped from "
            f"tournament #{args.tournament_id}",
        )

    elif args.tournament_command == "start":
        conn = get_connection()
        teams = list_tournament_teams(conn, args.tournament_id)
        if len(teams) < 2:
            conn.close()
            console.print("[red]✗[/red] Need at least 2 teams registered to start.")
            return
        team_names = [t.team_name for t in teams]
        bracket = generate_bracket(team_names)
        save_bracket_slots(conn, args.tournament_id, bracket)
        update_tournament_status(conn, args.tournament_id, "in-progress")
        conn.close()
        console.print(
            f"[green]✓[/green] Tournament #{args.tournament_id} started with "
            f"{len(teams)} teams, {len(bracket)} matches",
        )

    elif args.tournament_command == "bracket":
        conn = get_connection()
        tournament = get_tournament(conn, args.tournament_id)
        slots = load_bracket_slots(conn, args.tournament_id)
        teams = list_tournament_teams(conn, args.tournament_id)
        conn.close()

        if tournament is None:
            console.print(f"[red]✗[/red] Tournament #{args.tournament_id} not found")
            return

        console.print(f"[bold]Tournament: {tournament.name}[/bold] ({tournament.game_title})")
        console.print(f"Status: {tournament.status.value} | Teams: {len(teams)}")
        console.print("")

        if not slots:
            console.print(
                "[yellow]Bracket not yet generated. Start the tournament first.[/yellow]",
            )
            return

        slots_sorted = sorted(slots, key=lambda s: (-s["round"], s["position"]))
        for rnd, group in groupby(slots_sorted, key=lambda s: s["round"]):
            round_slots = list(group)
            round_name = round_slots[0].get("round_name", f"Round {rnd}")
            console.print(f"\n[bold]{round_name}[/bold]")
            for s in round_slots:
                t1 = s["team1_name"] or "TBD"
                t2 = s["team2_name"] or "TBD"
                status = f" → [green]{s['winner']}[/green]" if s["winner"] else ""
                console.print(f"  {t1} vs {t2}{status}")

        winner = get_tournament_winner(slots)
        if winner:
            console.print(f"\n[bold green]🏆 Champion: {winner}[/bold green]")

    elif args.tournament_command == "record-result":
        conn = get_connection()
        slots = load_bracket_slots(conn, args.tournament_id)
        if not slots:
            conn.close()
            console.print("[red]✗[/red] Bracket not generated yet. Start the tournament first.")
            return
        updated = advance_winner(slots, args.round, args.position, args.winner, args.score)
        save_bracket_slots(conn, args.tournament_id, updated)
        if is_bracket_complete(slots):
            update_tournament_status(conn, args.tournament_id, "completed")
            console.print("[green]✓[/green] Tournament completed!")
        conn.close()
        console.print(f"[green]✓[/green] Result recorded for tournament #{args.tournament_id}")

    else:
        console.print("[yellow]Unknown tournament subcommand[/yellow]")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:  # noqa: C901, PLR0912
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "player":
            if args.player_command == "create":
                cmd_player_create(args)
            elif args.player_command == "list":
                cmd_player_list(args)
            elif args.player_command == "delete":
                cmd_player_delete(args)

        elif args.command == "team":
            if args.team_command == "create":
                cmd_team_create(args)
            elif args.team_command == "list":
                cmd_team_list(args)
            elif args.team_command == "add-player":
                cmd_team_add_player(args)
            elif args.team_command == "remove-player":
                cmd_team_remove_player(args)
            elif args.team_command == "roster":
                cmd_team_roster(args)

        elif args.command == "availability":
            if args.avail_command == "set":
                cmd_avail_set(args)
            elif args.avail_command == "show":
                cmd_avail_show(args)
            elif args.avail_command == "team":
                cmd_avail_team(args)

        elif args.command == "dashboard":
            from esports_manager.dashboard import serve  # noqa: PLC0415

            serve(host=args.host, port=args.port)

        elif args.command == "match":
            if args.match_command == "create":
                _cmd_match_create(args)
            elif args.match_command == "list":
                _cmd_match_list(args)
            elif args.match_command == "record":
                _cmd_match_record(args)
            elif args.match_command == "delete":
                _cmd_match_delete(args)

        elif args.command == "record":
            _cmd_record(args)

        elif args.command == "tournament":
            _cmd_tournament(args)

        else:
            parser.print_help()

    except Exception as e:  # noqa: BLE001
        console.print(f"[red]✗ Unexpected error: {e}[/red]")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
