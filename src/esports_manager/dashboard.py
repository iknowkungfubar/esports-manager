"""FastAPI dashboard for eSports Manager."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from esports_manager.db import (
    get_connection,
    get_overlapping_availability,
    get_player_availability,
    get_team,
    get_team_availability,
    list_matches,
    list_players,
    list_roster,
    list_teams,
)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _read_template(name: str) -> str:
    path = TEMPLATES_DIR / name
    return path.read_text()


def create_app() -> FastAPI:
    app = FastAPI(title="eSports Manager", version="0.1.0")

    def _conn():
        return get_connection()

    # API Routes
    @app.get("/api/teams")
    def api_teams():
        """List teams with roster counts."""
        conn = _conn()
        teams = list_teams(conn)
        result = []
        for t in teams:
            roster = list_roster(conn, t.name)
            result.append({
                "name": t.name,
                "game_title": t.game_title.value,
                "description": t.description,
                "roster_count": len(roster),
            })
        conn.close()
        return {"teams": result}

    @app.get("/api/teams/{name}")
    def api_team_detail(name: str):
        """Team detail with roster and availability."""
        conn = _conn()
        team = get_team(conn, name)
        if team is None:
            conn.close()
            raise HTTPException(status_code=404, detail="Team not found")

        roster = list_roster(conn, name)
        avail = get_team_availability(conn, name)
        overlaps = get_overlapping_availability(conn, name)
        match_list = list_matches(conn, team_name=name)[:10]
        conn.close()

        return {
            "name": team.name,
            "game_title": team.game_title.value,
            "description": team.description,
            "roster": [
                {"player_name": r.player_name, "gamertag": r.gamertag, "role": r.role.value}
                for r in roster
            ],
            "availability": {
                player: [{"day": DAY_NAMES[a.day_of_week], "hours": f"{a.start_hour:02d}:00-{a.end_hour:02d}:00"} for a in slots]
                for player, slots in avail.items()
            },
            "best_times": [
                {"day": DAY_NAMES[o["day_of_week"]], "start": o["start_hour"], "end": o["end_hour"], "players": o["player_count"]}
                for o in overlaps[:5]
            ],
            "matches": [
                {"id": m.id, "opponent": m.opponent, "match_date": m.match_date,
                 "match_time": m.match_time, "format": m.format.value, "status": m.status.value}
                for m in match_list
            ],
        }

    @app.get("/api/players")
    def api_players():
        """List all players."""
        conn = _conn()
        players = list_players(conn)
        conn.close()
        return {
            "players": [
                {"name": p.name, "gamertag": p.gamertag, "game_title": p.game_title.value,
                 "skill_level": p.skill_level.value, "discord": p.discord}
                for p in players
            ]
        }

    @app.get("/api/players/{gamertag}/availability")
    def api_player_availability(gamertag: str):
        """Get player availability."""
        conn = _conn()
        slots = get_player_availability(conn, gamertag)
        conn.close()
        return {
            "gamertag": gamertag,
            "availability": [
                {"day": DAY_NAMES[s.day_of_week], "day_num": s.day_of_week,
                 "start": s.start_hour, "end": s.end_hour}
                for s in slots
            ]
        }

    # Dashboard pages
    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_read_template("dashboard.html"))

    @app.get("/teams/{name}", response_class=HTMLResponse)
    def team_page(name: str):
        conn = _conn()
        team = get_team(conn, name)
        conn.close()
        if team is None:
            raise HTTPException(status_code=404)
        html = _read_template("team.html").replace("{{ team_name }}", name)
        return HTMLResponse(content=html)

    @app.get("/api/tournaments")
    def api_tournaments():
        """List tournaments."""
        from esports_manager.db import list_tournaments, list_tournament_teams
        conn = _conn()
        tournaments = list_tournaments(conn)
        result = []
        for t in tournaments:
            teams = list_tournament_teams(conn, t.id)
            result.append({
                "id": t.id, "name": t.name, "game_title": t.game_title,
                "status": t.status.value, "max_teams": t.max_teams,
                "team_count": len(teams),
            })
        conn.close()
        return {"tournaments": result}

    @app.get("/tournaments", response_class=HTMLResponse)
    def tournaments_page():
        return HTMLResponse(content=_read_template("tournaments.html"))

    return app


def serve(host: str = "127.0.0.1", port: int = 8555) -> None:
    """Start the dashboard server."""
    import uvicorn
    app = create_app()
    print(f"  eSports Manager Dashboard -> http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
