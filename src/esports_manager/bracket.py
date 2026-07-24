"""Tournament bracket generation engine.

Supports single-elimination brackets with seeding,
auto-advancement, and byes for non-power-of-2 team counts.
"""

from __future__ import annotations

import math
from typing import Any


def _next_power_of_2(n: int) -> int:
    """Get the next power of 2 >= n."""
    return 2 ** math.ceil(math.log2(n)) if n > 0 else 0


def _total_rounds(num_teams: int) -> int:
    """Calculate number of rounds needed for single elimination."""
    if num_teams <= 1:
        return 0
    return math.ceil(math.log2(num_teams))


def generate_bracket(teams: list[str]) -> list[dict[str, Any]]:
    """Generate a single-elimination bracket from a list of team names.

    Args:
        teams: List of team names. If not a power of 2, byes are added.

    Returns:
        List of bracket slot dicts, each with:
            round: int (0 = final)
            position: int
            team1: str (empty if bye)
            team2: str (empty if bye)
            round_name: str

    """
    count = len(teams)
    if count < 2:
        return []

    # Pad with byes to next power of 2
    padded_count = _next_power_of_2(count)
    slots = list(teams) + [""] * (padded_count - count)

    # Seed the bracket
    # Standard seeding: 1 vs last, 2 vs second-last, etc.
    seeded: list[str] = [""] * padded_count
    for i in range(padded_count // 2):
        seeded[i * 2] = slots[i]
        seeded[i * 2 + 1] = slots[-(i + 1)]

    total_r = _total_rounds(padded_count)
    bracket: list[dict[str, Any]] = []

    for rnd in range(total_r, 0, -1):
        if rnd == total_r:
            matches_in_round = padded_count // 2
        else:
            matches_in_round = 2 ** (rnd - 1)

        if rnd == total_r:
            # First round — use seeded teams
            for pos in range(matches_in_round):
                bracket.append(
                    {
                        "round": total_r - rnd,
                        "position": pos,
                        "team1": seeded[pos * 2] if seeded[pos * 2] else "",
                        "team2": seeded[pos * 2 + 1] if seeded[pos * 2 + 1] else "",
                        "winner": "",
                        "round_name": _round_name(total_r - rnd, total_r),
                    }
                )
        else:
            # Later rounds — slots are placeholders
            for pos in range(matches_in_round):
                bracket.append(
                    {
                        "round": total_r - rnd,
                        "position": pos,
                        "team1": "",
                        "team2": "",
                        "winner": "",
                        "round_name": _round_name(total_r - rnd, total_r),
                    }
                )

    # Fix first round for non-power-of-2: byes auto-advance
    # Teams facing a bye (empty opponent) get an auto-win
    for slot in bracket:
        if slot["round"] == 0:
            if slot["team1"] and not slot["team2"]:
                slot["winner"] = "team1"
            elif slot["team2"] and not slot["team1"]:
                slot["winner"] = "team2"

    return bracket


def _round_name(round_num: int, total_rounds: int) -> str:
    """Get a human-readable name for a round."""
    if total_rounds == 0:
        return "Final"
    if round_num == total_rounds:
        return "Final"
    if round_num == total_rounds - 1:
        return "Semi-Finals"
    if round_num == total_rounds - 2:
        return "Quarter-Finals"
    if round_num == 0:
        return "Round 1"
    return f"Round {round_num + 1}"


def advance_winner(
    bracket: list[dict[str, Any]],
    round_num: int,
    position: int,
    winner: str,
    score: str = "",
) -> list[dict[str, Any]]:
    """Record a match result and advance the winner.

    Args:
        bracket: Current bracket state.
        round_num: Round of the match (0 = first round).
        position: Position within the round.
        winner: "team1" or "team2".
        score: Score string (e.g. "3-1").

    Returns:
        Updated bracket.

    """
    slots = list(bracket)

    # Find and update the match
    match_slot = None
    for slot in slots:
        if slot["round"] == round_num and slot["position"] == position:
            slot["winner"] = winner
            slot["score"] = score
            match_slot = slot
            break

    if match_slot is None:
        return bracket

    # Determine which team won
    winning_team = match_slot["team1"] if winner == "team1" else match_slot["team2"]

    if not winning_team:
        return bracket

    # Advance to next round (higher round number)
    next_round = round_num + 1
    next_position = position // 2

    for slot in slots:
        if slot["round"] == next_round and slot["position"] == next_position:
            if position % 2 == 0:
                slot["team1"] = winning_team
            else:
                slot["team2"] = winning_team
            break

    return slots


def is_bracket_complete(bracket: list[dict[str, Any]]) -> bool:
    """Check if all matches in the bracket have a winner."""
    for slot in bracket:
        if not slot["team1"] and not slot["team2"]:
            continue  # Future round, empty
        if slot["team1"] and slot["team2"] and not slot["winner"]:
            return False
    return True


def get_tournament_winner(bracket: list[dict[str, Any]]) -> str | None:
    """Get the tournament winner from a completed bracket."""
    if not is_bracket_complete(bracket):
        return None
    # Winner is in the final match (highest round, position 0)
    final = [s for s in bracket if s["position"] == 0]
    if not final:
        return None
    final_slot = max(final, key=lambda s: s["round"])
    if final_slot["winner"] == "team1":
        return final_slot["team1"]
    if final_slot["winner"] == "team2":
        return final_slot["team2"]
    return None
