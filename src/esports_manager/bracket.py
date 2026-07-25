# Copyright (c) 2024-2025 iknowkungfubar
# Licensed under the MIT License. See LICENSE file for details.

"""Bracket generation and management for tournaments."""

from __future__ import annotations

from math import log2
from typing import Any


def _round_name(round_idx: int, total_rounds: int) -> str:
    """Generate a human-readable round name."""
    if round_idx == total_rounds - 1:
        return "Final"
    if round_idx == total_rounds - 2:
        return "Semi-finals"
    if round_idx == total_rounds - 3:
        return "Quarter-finals"
    return f"Round {round_idx + 1}"


def _next_power_of_two(n: int) -> int:
    """Get the next power of 2 >= n."""
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def _standard_seeding(teams: list[str], total_teams: int) -> list[str]:
    """Generate standard tournament seeding order.

    For a power-of-2 bracket, standard seeding pairs:
    - Seed 1 vs Seed N
    - Seed 2 vs Seed N-1
    - Seed 3 vs Seed N-2
    - etc.

    This produces the bracket order: [1, N, 2, N-1, 3, N-2, ...]
    """
    if len(teams) <= 1:
        return teams + [""] * (total_teams - len(teams))

    seeds = list(range(1, len(teams) + 1))
    # Standard tournament seeding algorithm
    seeded_order: list[int] = []
    left, right = 0, len(seeds) - 1
    while left <= right:
        if left == right:
            seeded_order.append(seeds[left])
        else:
            seeded_order.append(seeds[left])
            seeded_order.append(seeds[right])
        left += 1
        right -= 1

    # Map back to team names
    result = []
    for seed_idx in seeded_order:
        if seed_idx <= len(teams):
            result.append(teams[seed_idx - 1])
        else:
            result.append("")

    # Pad to total_teams
    result.extend([""] * (total_teams - len(result)))
    return result


def _create_first_round(
    teams: list[str],
    total_teams: int,
    total_rounds: int,
) -> list[dict[str, Any]]:
    """Create the first round of bracket slots with seeded teams."""
    seeded = _standard_seeding(teams, total_teams)
    matches_in_round = total_teams // 2

    return [
        {
            "round": 0,
            "position": pos,
            "team1": seeded[pos * 2] or "",
            "team2": seeded[pos * 2 + 1] or "",
            "winner": "",
            "round_name": _round_name(0, total_rounds),
        }
        for pos in range(matches_in_round)
    ]


def _create_later_rounds(total_rounds: int) -> list[dict[str, Any]]:
    """Create placeholder slots for later rounds (round 1 onwards)."""
    bracket: list[dict[str, Any]] = []
    for rnd in range(1, total_rounds):
        matches_in_round = 2 ** (total_rounds - rnd - 1)
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
    if total_teams <= 1:
        return

    first_round = [s for s in bracket if s["round"] == 0]
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
        Round 0 = first round, higher rounds = later rounds.

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
        # Skip empty slots (future rounds not yet populated)
        if not slot["team1"] and not slot["team2"]:
            continue
        # Match has both teams but no winner
        if slot["team1"] and slot["team2"] and not slot["winner"]:
            return False
        # Match has only one team (bye) but no winner recorded
        if (slot["team1"] or slot["team2"]) and not slot["winner"]:
            # Actually, _apply_byes should have set winner for byes
            # If we reach here, it's an incomplete bye match
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
