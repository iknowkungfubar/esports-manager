# Copyright (c) 2024-2025 iknowkungfubar
# Licensed under the MIT License. See LICENSE file for details.

"""Semantic validation of the README project-structure tree.

The fenced tree under ``## Project Structure`` in README.md is an explicitly
owned documentation contract describing the repository layout. These tests
parse that tree into a normalized set of paths and assert its *meaning*
against real filesystem state:

* every entry listed in the tree exists on disk, and
* every Python source file under the documented source/test directories is
  represented in the tree.

This is the regression guard for the documented layout: it fails when the
README tree drifts from the actual sources (e.g. renaming a module without
updating the tree), which is exactly the failure mode this contract exists to
prevent.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

# Documented conventions: __init__.py is never enumerated in the tree, and
# template HTML files are collapsed into their containing directory entry.
OMITTED_FILES = {"src/esports_manager/__init__.py"}


def readme_tree_paths() -> set[str]:
    """Parse the README structure tree into normalized relative paths.

    Directories are returned with a trailing slash; files without one.
    """
    text = README.read_text(encoding="utf-8")
    match = re.search(r"## Project Structure\n\n```\n(.*?)\n```", text, re.DOTALL)
    assert match, "README.md must contain a fenced 'Project Structure' tree"
    lines = match.group(1).splitlines()

    paths: set[str] = set()
    stack: list[str] = []  # directory path segments, indexed by tree depth
    root: str | None = None  # first line names the tree's root directory
    for line in lines:
        # Each tree level is a 4-character glyph column ("│   ", "├── ", "└── ").
        # The entry's depth is one past the cell holding its ├/└ connector.
        depth = 0
        for i in range(0, len(line) - len(line) % 4, 4):
            if "├" in line[i : i + 4] or "└" in line[i : i + 4]:
                depth = i // 4 + 1
        name = re.split(r"\s+#", line[depth * 4 :], maxsplit=1)[0].strip()
        if not name:
            continue
        if root is None:
            root = name.rstrip("/")
        stack = stack[: max(depth - 1, 0)]
        is_dir = name.endswith("/")
        name = name.rstrip("/")
        if name == root:
            continue  # the root line is not a real path entry
        rel = "/".join([*stack, name])
        if is_dir:
            stack.append(name)
            paths.add(rel + "/")
        else:
            paths.add(rel)
    return paths


def listed_files(paths: set[str]) -> set[str]:
    return {p for p in paths if not p.endswith("/")}


def listed_dirs(paths: set[str]) -> set[str]:
    return {p.rstrip("/") for p in paths if p.endswith("/")}


def test_readme_tree_entries_exist_on_disk() -> None:
    paths = readme_tree_paths()
    missing = [p for p in sorted(paths) if not (REPO_ROOT / p.rstrip("/")).exists()]
    assert not missing, f"README structure tree lists entries that do not exist: {missing}"


def test_readme_tree_covers_all_documented_sources() -> None:
    tree = readme_tree_paths()
    files = listed_files(tree)
    dirs = listed_dirs(tree)

    # Every application source module under the documented source root must
    # be represented in the tree (the exact failure mode this commit fixed:
    # bracket.py existed but was omitted).
    unlisted: list[str] = []
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in OMITTED_FILES:
            continue
        if rel not in files:
            unlisted.append(rel)
    assert not unlisted, f"Python sources missing from the README structure tree: {unlisted}"
    # The test file the tree documents must be listed.
    assert "tests/test_core.py" in files, "tree must list tests/test_core.py"
    # The directories the tree documents must themselves exist as entries.
    assert "src/esports_manager" in dirs, "tree must list the src/esports_manager directory"
    assert "tests" in dirs, "tree must list the tests directory"
