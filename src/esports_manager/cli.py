"""CLI interface for the eSports Manager."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from esports_manager.db import (
    add_roster_entry,
    delete_player,
    delete_team,
    get_connection,
    get_overlapping_availability,
    get_player,
    get_player_availability,
    get_team,
    get_team_availability,
    list_players,
    list_roster,
    list_teams,
    remove_availability,
    remove_roster_entry,
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
    Player,
    PlayerRole,
    RosterEntry,
    SkillLevel,
    Team,
)

console = Console()

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="esports",
        description="eSports team/club management platform",
    )

    sub = parser.add_subparsers(dest="command", help="Command")

    # player
    p = sub.add_parser("player", help="Manage players")
    ps = p.add_subparsers(dest="player_command")

    pc = ps.add_parser("create", help="Create a player")
    pc.add_argument("name", type=str, help="Display name")
    pc.add_argument("--gamertag", type=str, required=True, help="Unique gamertag")
    pc.add_argument("--email", type=str, default="", help="Email address")
    pc.add_argument("--discord", type=str, default="", help="Discord handle")
    pc.add_argument("--game", type=str, default="other", help="Game title")
    pc.add_argument("--skill", type=str, default="intermediate", help="Skill level")

    ps.add_parser("list", help="List players")

    pd = ps.add_parser("delete", help="Delete a player")
    pd.add_argument("gamertag", type=str, help="Gamertag to delete")

    # team
    t = sub.add_parser("team", help="Manage teams")
    ts = t.add_subparsers(dest="team_command")

    tc = ts.add_parser("create", help="Create a team")
    tc.add_argument("name", type=str, help="Team name")
    tc.add_argument("--game", type=str, default="other", help="Game title")
    tc.add_argument("--desc", type=str, default="", help="Description")

    ts.add_parser("list", help="List teams")

    ta = ts.add_parser("add-player", help="Add player to team")
    ta.add_argument("team", type=str, help="Team name")
    ta.add_argument("--gamertag", type=str, required=True, help="Player gamertag")
    ta.add_argument("--role", type=str, default="player", help="Roster role")

    tr = ts.add_parser("remove-player", help="Remove player from team")
    tr.add_argument("team", type=str, help="Team name")
    tr.add_argument("--gamertag", type=str, required=True, help="Player gamertag")

    tros = ts.add_parser("roster", help="Show team roster")
    tros.add_argument("name", type=str, help="Team name")

    # availability
    a = sub.add_parser("availability", help="Manage availability")
    av = a.add_subparsers(dest="avail_command")

    avs = av.add_parser("set", help="Set availability slot")
    avs.add_argument("--player", type=str, required=True, help="Player gamertag")
    avs.add_argument("--day", type=int, required=True, help="Day of week (0=Mon, 6=Sun)")
    avs.add_argument("--start", type=int, required=True, help="Start hour (0-23)")
    avs.add_argument("--end", type=int, required=True, help="End hour (0-23)")

    av.show = av.add_parser("show", help="Show player availability")
    av.show.add_argument("--player", type=str, required=True, help="Player gamertag")

    a_team = av.add_parser("team", help="Show team availability")
    a_team.add_argument("--team", type=str, required=True, help="Team name")

    # match commands
    m = sub.add_parser("match", help="Manage matches/scrims")
    ms = m.add_subparsers(dest="match_command")

    mc = ms.add_parser("create", help="Schedule a match")
    mc.add_argument("team", type=str, help="Your team name")
    mc.add_argument("--opponent", type=str, required=True, help="Opponent name")
    mc.add_argument("--date", type=str, required=True, help="Match date (YYYY-MM-DD)")
    mc.add_argument("--time", type=str, default="", help="Match time (HH:MM)")
    mc.add_argument("--format", type=str, default="bo3", help="Format (bo1/bo3/bo5)")
    mc.add_argument("--notes", type=str, default="", help="Notes")

    m_list = ms.add_parser("list", help="List matches")
    m_list.add_argument("--team", type=str, default=None, help="Filter by team")
    m_list.add_argument("--status", type=str, default=None, help="Filter by status")

    result = ms.add_parser("record", help="Record a match result")
    result.add_argument("match_id", type=int, help="Match ID")
    result.add_argument("--team-score", type=int, required=True, help="Your team score")
    result.add_argument("--opponent-score", type=int, required=True, help="Opponent score")
    result.add_argument("--mvp", type=str, default="", help="MVP gamertag")
    result.add_argument("--maps", type=str, default="", help="Map results (JSON)")

    m_del = ms.add_parser("delete", help="Delete a match")
    m_del.add_argument("match_id", type=int, help="Match ID")

    record = sub.add_parser("record", help="Show team's W/L/T record")
    record.add_argument("team", type=str, help="Team name")

    # tournament commands
    tour = sub.add_parser("tournament", help="Manage tournaments")
    ts = tour.add_subparsers(dest="tournament_command")

    tc = ts.add_parser("create", help="Create a tournament")
    tc.add_argument("name", type=str, help="Tournament name")
    tc.add_argument("--game", type=str, default="other", help="Game title")
    tc.add_argument("--max-teams", type=int, default=8, help="Max teams")

    ts.add_parser("list", help="List tournaments")

    t_reg = ts.add_parser("register-team", help="Register a team")
    t_reg.add_argument("tournament_id", type=int, help="Tournament ID")
    t_reg.add_argument("--team", type=str, required=True, help="Team name")
    t_reg.add_argument("--seed", type=int, default=0, help="Seed number")

    t_unreg = ts.add_parser("drop-team", help="Remove a team from tournament")
    t_unreg.add_argument("tournament_id", type=int, help="Tournament ID")
    t_unreg.add_argument("--team", type=str, required=True, help="Team name")

    t_start = ts.add_parser("start", help="Generate bracket and start tournament")
    t_start.add_argument("tournament_id", type=int, help="Tournament ID")

    t_bracket = ts.add_parser("bracket", help="View tournament bracket")
    t_bracket.add_argument("tournament_id", type=int, help="Tournament ID")

    t_result = ts.add_parser("record-result", help="Record bracket match result")
    t_result.add_argument("tournament_id", type=int, help="Tournament ID")
    t_result.add_argument("--round", type=int, required=True, help="Round number")
    t_result.add_argument("--position", type=int, required=True, help="Position in round")
    t_result.add_argument("--winner", type=str, required=True, help="team1 or team2")
    t_result.add_argument("--score", type=str, default="", help="Score (e.g. 3-1)")

    # dashboard
    dash = sub.add_parser("dashboard", help="Start web dashboard")
    dash.add_argument("--host", type=str, default="127.0.0.1", help="Host (default: 127.0.0.1)")
    dash.add_argument("--port", "-p", type=int, default=8555, help="Port (default: 8555)")

    return parser


def cmd_player_create(args: argparse.Namespace) -> None:
    """Create a new player."""
    game = GameTitle(args.game) if hasattr(GameTitle, args.game.upper().replace("-", "_")) else GameTitle.OTHER
    skill = SkillLevel(args.skill) if hasattr(SkillLevel, args.skill.upper().replace("-", "_")) else SkillLevel.INTERMEDIATE

    player = Player(
        name=args.name,
        gamertag=args.gamertag,
        email=args.email,
        discord=args.discord,
        game_title=game,
        skill_level=skill,
    )
    conn = get_connection()
    upsert_player(conn, player)
    conn.close()
    console.print(f"[green]✓[/green] Player [bold]{player.gamertag}[/bold] created ({player.name})")


def cmd_player_list() -> None:
    """List all players."""
    conn = get_connection()
    players = list_players(conn)
    conn.close()

    if not players:
        console.print("[yellow]No players yet.[/yellow]")
        return

    table = Table(title="Players")
    table.add_column("Gamertag", style="cyan")
    table.add_column("Name")
    table.add_column("Game")
    table.add_column("Skill")
    table.add_column("Discord")

    for p in players:
        table.add_row(p.gamertag, p.name, p.game_title.value, p.skill_level.value, p.discord)
    console.print(table)


def cmd_player_delete(args: argparse.Namespace) -> None:
    """Delete a player."""
    conn = get_connection()
    delete_player(conn, args.gamertag)
    conn.close()
    console.print(f"[green]✓[/green] Player [bold]{args.gamertag}[/bold] deleted")


def cmd_team_create(args: argparse.Namespace) -> None:
    """Create a new team."""
    team = Team(
        name=args.name,
        game_title=GameTitle(args.game) if hasattr(GameTitle, args.game.upper().replace("-", "_")) else GameTitle.OTHER,
        description=args.desc,
    )
    conn = get_connection()
    upsert_team(conn, team)
    conn.close()
    console.print(f"[green]✓[/green] Team [bold]{team.name}[/bold] created")


def cmd_team_list() -> None:
    """List all teams."""
    conn = get_connection()
    teams = list_teams(conn)
    conn.close()

    if not teams:
        console.print("[yellow]No teams yet.[/yellow]")
        return

    table = Table(title="Teams")
    table.add_column("Name", style="cyan")
    table.add_column("Game")
    table.add_column("Description")
    table.add_column("Roster", justify="right")

    for t in teams:
        conn2 = get_connection()
        roster = list_roster(conn2, t.name)
        conn2.close()
        table.add_row(t.name, t.game_title.value, t.description[:40], str(len(roster)))
    console.print(table)


def cmd_team_add_player(args: argparse.Namespace) -> None:
    """Add a player to a team."""
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

    role = PlayerRole(args.role) if hasattr(PlayerRole, args.role.upper()) else PlayerRole.PLAYER
    entry = RosterEntry(team_name=args.team, player_name=player.name, gamertag=args.gamertag, role=role)
    add_roster_entry(conn, entry)
    conn.close()
    console.print(f"[green]✓[/green] [bold]{args.gamertag}[/bold] added to [bold]{args.team}[/bold] as {role.value}")


def cmd_team_remove_player(args: argparse.Namespace) -> None:
    """Remove a player from a team."""
    conn = get_connection()
    remove_roster_entry(conn, args.team, args.gamertag)
    conn.close()
    console.print(f"[green]✓[/green] [bold]{args.gamertag}[/bold] removed from [bold]{args.team}[/bold]")


def cmd_team_roster(args: argparse.Namespace) -> None:
    """Show team roster."""
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
            players = o["players"].split(",")
            console.print(f"  {DAY_NAMES[o['day_of_week']]} {o['start_hour']:02d}:00-{o['end_hour']:02d}:00 — {o['player_count']} player(s)")


def cmd_avail_set(args: argparse.Namespace) -> None:
    """Set availability for a player."""
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
    console.print(f"[green]✓[/green] Availability set for [bold]{args.player}[/bold] on {DAY_NAMES[args.day]} {args.start}:00-{args.end}:00")


def cmd_avail_show(args: argparse.Namespace) -> None:
    """Show player availability."""
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
    """Show team availability overview."""
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
        times = [f"{DAY_NAMES[s.day_of_week]} {s.start_hour:02d}:00-{s.end_hour:02d}:00" for s in slots]
        console.print(f"  [cyan]{player_name}[/cyan]: {', '.join(times)}")

    if overlaps:
        console.print("\n[bold]Overlapping Slots:[/bold]")
        for o in overlaps[:5]:
            console.print(f"  {DAY_NAMES[o['day_of_week']]} {o['start_hour']:02d}:00-{o['end_hour']:02d}:00 — {o['player_count']} players")


# ---------------------------------------------------------------------------
# Match commands
# ---------------------------------------------------------------------------


def _cmd_match_create(args: argparse.Namespace) -> None:
    """Schedule a new match."""
    from esports_manager.db import create_match
    match = Match(
        team_name=args.team,
        opponent=args.opponent,
        match_date=args.date,
        match_time=args.time,
        format=MatchFormat(args.format) if hasattr(MatchFormat, args.format.upper().replace("-", "_")) else MatchFormat.BO3,
        notes=args.notes,
    )
    conn = get_connection()
    match_id = create_match(conn, match)
    conn.close()
    console.print(f"[green]✓[/green] Match #{match_id} scheduled — [bold]{args.team}[/bold] vs {args.opponent} on {args.date}")


def _cmd_match_list(args: argparse.Namespace) -> None:
    """List matches."""
    from esports_manager.db import get_match_result, list_matches
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
        table.add_row(str(m.id), m.match_date, m.team_name, m.opponent, m.format.value, m.status.value)
    console.print(table)


def _cmd_match_record(args: argparse.Namespace) -> None:
    """Record a match result."""
    from esports_manager.db import get_match, record_match_result

    conn = get_connection()
    match = get_match(conn, args.match_id)
    if match is None:
        conn.close()
        console.print(f"[red]✗[/red] Match #{args.match_id} not found")
        return

    winner = "team" if args.team_score > args.opponent_score else "opponent" if args.opponent_score > args.team_score else "draw"
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

    status_text = f"[green]WON[/green]" if winner == "team" else f"[red]LOST[/red]" if winner == "opponent" else "[yellow]DRAW[/yellow]"
    console.print(f"[green]✓[/green] Result recorded: {status_text} {args.team_score}-{args.opponent_score}")


def _cmd_match_delete(args: argparse.Namespace) -> None:
    """Delete a match."""
    from esports_manager.db import delete_match
    conn = get_connection()
    delete_match(conn, args.match_id)
    conn.close()
    console.print(f"[green]✓[/green] Match #{args.match_id} deleted")


def _cmd_record(args: argparse.Namespace) -> None:
    """Show team's W/L/T record."""
    from esports_manager.db import get_team_record
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


def _cmd_tournament(args: argparse.Namespace) -> None:
    """Dispatch tournament subcommands."""
    from esports_manager.db import (
        create_tournament,
        get_tournament,
        list_tournament_teams,
        list_tournaments,
        load_bracket_slots,
        register_tournament_team,
        save_bracket_slots,
        unregister_tournament_team,
        update_tournament_status,
    )
    from esports_manager.models import Tournament, TournamentTeam

    if args.tournament_command == "create":
        t = Tournament(name=args.name, game_title=args.game, max_teams=args.max_teams)
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
        register_tournament_team(conn, TournamentTeam(
            tournament_id=args.tournament_id, team_name=args.team, seed=args.seed,
        ))
        conn.close()
        console.print(f"[green]✓[/green] [bold]{args.team}[/bold] registered for tournament #{args.tournament_id}")

    elif args.tournament_command == "drop-team":
        conn = get_connection()
        unregister_tournament_team(conn, args.tournament_id, args.team)
        conn.close()
        console.print(f"[green]✓[/green] [bold]{args.team}[/bold] dropped from tournament #{args.tournament_id}")

    elif args.tournament_command == "start":
        from esports_manager.bracket import generate_bracket
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
        console.print(f"[green]✓[/green] Tournament #{args.tournament_id} started with {len(teams)} teams, {len(bracket)} matches")

    elif args.tournament_command == "bracket":
        from esports_manager.bracket import get_tournament_winner
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
            console.print("[yellow]Bracket not yet generated. Start the tournament first.[/yellow]")
            return

        # Group by round
        from itertools import groupby
        slots_sorted = sorted(slots, key=lambda s: (-s["round"], s["position"]))
        for rnd, group in groupby(slots_sorted, key=lambda s: s["round"]):
            round_slots = list(group)
            round_name = round_slots[0].get("round_name", f"Round {rnd}") if "round_name" in round_slots[0] else f"Round {rnd}"
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
        from esports_manager.bracket import advance_winner
        conn = get_connection()
        slots = load_bracket_slots(conn, args.tournament_id)
        if not slots:
            conn.close()
            console.print("[red]✗[/red] Bracket not generated yet. Start the tournament first.")
            return
        updated = advance_winner(slots, args.round, args.position, args.winner, args.score)
        save_bracket_slots(conn, args.tournament_id, updated)
        # Check if tournament is complete
        from esports_manager.bracket import is_bracket_complete
        if is_bracket_complete(slots):
            update_tournament_status(conn, args.tournament_id, "completed")
            console.print("[green]✓[/green] Tournament completed!")
        conn.close()
        console.print(f"[green]✓[/green] Result recorded for tournament #{args.tournament_id}")

    else:
        console.print("[yellow]Unknown tournament subcommand[/yellow]")


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "player":
            if args.player_command == "create":
                cmd_player_create(args)
            elif args.player_command == "list":
                cmd_player_list()
            elif args.player_command == "delete":
                cmd_player_delete(args)
        elif args.command == "team":
            if args.team_command == "create":
                cmd_team_create(args)
            elif args.team_command == "list":
                cmd_team_list()
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
            from esports_manager.dashboard import serve
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
    except Exception as e:
        console.print(f"[red]✗ Unexpected error: {e}[/red]")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
