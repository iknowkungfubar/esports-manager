# eSports Manager

**Team & club management platform for amateur/semi-pro eSports organizations.**

Manage players, rosters, availability, and practice scheduling — all from the CLI or web dashboard.

## Features

- **Player profiles** — gamertag, game title, skill level, Discord, email
- **Team management** — create teams, assign players with roles (captain, coach, player, sub)
- **Roster tracking** — see who's on which team and in what role
- **Availability** — players set weekly availability, system finds overlapping practice times
- **Dashboard** — web UI for team overview, roster, and availability

## Quick Start

```bash
# Install
uv sync --group dev

# Create a player
uv run esports player create "Alice" --gamertag "alice#1234" --game valorant --skill semi-pro

# Create a team
uv run esports team create "Valorants" --game valorant

# Add player to team
uv run esports team add-player Valorants --gamertag "alice#1234" --role captain

# Set availability
uv run esports availability set --player "alice#1234" --day 0 --start 18 --end 21

# Show team roster with availability
uv run esports team roster Valorants

# Start the dashboard
uv run python -c "from esports_manager.dashboard import serve; serve()"
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `player create <name> --gamertag G` | Create a player |
| `player list` | List all players |
| `player delete <gamertag>` | Delete a player |
| `team create <name> --game G` | Create a team |
| `team list` | List all teams |
| `team add-player <team> --gamertag G --role R` | Add player to team |
| `team remove-player <team> --gamertag G` | Remove player from team |
| `team roster <name>` | Show roster with availability |
| `availability set --player G --day D --start S --end E` | Set availability slot |
| `availability show --player G` | Show player availability |
| `availability team --team T` | Show team availability overview |

## Run Tests

```bash
uv run --group dev pytest tests/ --cov=esports_manager
```

## License

MIT
