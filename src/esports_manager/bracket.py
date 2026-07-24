# Copyright (c) 2024-2025 iknowkungfubar
# Licensed under the MIT License. See LICENSE file for details.

"""Bracket generation and management for tournaments."""

from __future__ import annotations

from math import log2
from typing import Any


def _round_name(round_idx: int, total_rounds: int) -> str:
    """Generate a human-readable round name."""
    if round_idx == 0:
        return "Final"
    if round_idx == 1:
        return "Semi-finals"
    if round_idx == 2:
        return "Quarter-finals"
    return f"Round {total_rounds - round_idx}"


def _next_power_of_two(n: int) -> int:
    """Get the next power of 2 >= n."""
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def _create_first_round(
    teams: list[str],
    total_teams: int,
    total_rounds: int,
) -> list[dict[str, Any]]:
    """Create the first round of bracket slots with seeded teams."""
    padded = teams + [""] * (total_teams - len(teams))
    matches_in_round = total_teams // 2

    return [
        {
            "round": total_rounds - 1,
            "position": pos,
            "team1": padded[pos * 2] or "",
            "team2": padded[pos * 2 + 1] or "",
            "winner": "",
            "round_name": _round_name(total_rounds - 1, total_rounds),
        }
        for pos in range(matches_in_round)
    ]


def _create_later_rounds(total_rounds: int) -> list[dict[str, Any]]:
    """Create placeholder slots for later rounds."""
    bracket: list[dict[str, Any]] = []
    for rnd in range(total_rounds - 2, -1, -1):
        matches_in_round = 2**rnd
        bracket.extend(
            {
                "round": rnd,
                "position": pos,
                "team1": "",
                "team2": "",
                "winner": "",
                "round_name": _round_name(rnd, total_rounds),
            }
            for pos in range(matches_in_round)
        )
    return bracket


def _apply_byes(bracket: list[dict[str, Any]], total_teams: int) -> None:
    """Auto-advance teams that get byes in the first round."""
    if total_teams == len([t for t in bracket if t["team1"]]):
        return

    first_round = [s for s in bracket if s["round"] == len(bracket).bit_length() - 1]
    for slot in first_round:
        if slot["team1"] and not slot["team2"]:
            slot["winner"] = "team1"
        elif slot["team2"] and not slot["team1"]:
            slot["winner"] = "team2"


def generate_bracket(teams: list[str]) -> list[dict[str, Any]]:
    """Generate a single-elimination bracket from a list of team names.

    Args:
        teams: List of team names.

    Returns:
        List of bracket slots (dicts with round, position, team1, team2, winner, round_name).

    """
    if len(teams) < 2:
        return []

    total_teams = _next_power_of_two(len(teams))
    total_rounds = int(log2(total_teams))

    bracket: list[dict[str, Any]] = []
    bracket.extend(_create_first_round(teams, total_teams, total_rounds))
    bracket.extend(_create_later_rounds(total_rounds))
    _apply_byes(bracket, len(teams))

    return bracket


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

    # Advance to next round
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
