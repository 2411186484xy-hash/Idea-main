"""README command table is the CLI contract: parser and README must agree."""

from __future__ import annotations

import re
from pathlib import Path

from cli import build_parser

README = Path(__file__).resolve().parent.parent / "README.md"


def _readme_commands() -> list[str]:
    text = README.read_text(encoding="utf-8")
    return re.findall(r"^\| `([a-z0-9-]+)`", text, re.M)


def _parser_commands() -> set[str]:
    parser = build_parser()
    subparsers = parser._subparsers._group_actions[0]  # noqa: SLF001 - stable argparse surface
    return set(subparsers.choices.keys())


def test_readme_table_matches_parser():
    table = _readme_commands()
    assert len(table) == 21, f"README table must list 21 commands, found {len(table)}"
    assert len(set(table)) == 21, "README table has duplicates"
    assert set(table) == _parser_commands(), (
        f"README/parser drift: only-in-readme={sorted(set(table) - _parser_commands())} "
        f"only-in-parser={sorted(_parser_commands() - set(table))}"
    )


def test_every_parser_command_implemented_or_declared():
    """Each command either has logic in main() or is declared in NOT_IMPLEMENTED."""
    import cli

    declared = set(cli.NOT_IMPLEMENTED)
    parser_cmds = _parser_commands()
    stubbed_and_missing = declared - parser_cmds
    assert not stubbed_and_missing, f"stubs declared but not wired: {stubbed_and_missing}"
