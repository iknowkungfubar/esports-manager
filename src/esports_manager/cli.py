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
        else:
            parser.print_help()
    except Exception as e:
        console.print(f"[red]✗ Unexpected error: {e}[/red]")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
