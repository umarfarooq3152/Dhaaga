"""Release-contract checks for the 100-persona search evaluation corpus."""

import re
from pathlib import Path


CORPUS = Path(__file__).parents[3] / "docs" / "SEARCH_PERSONA_CORPUS.md"


def _persona_rows() -> list[tuple[int, str, str]]:
    rows = []
    pattern = re.compile(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$")
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            rows.append((int(match.group(1)), match.group(2), match.group(3)))
    return rows


def test_search_persona_corpus_keeps_all_100_numbered_scenarios():
    rows = _persona_rows()

    assert [number for number, _, _ in rows] == list(range(1, 101))


def test_every_persona_has_a_message_and_observable_expected_outcome():
    for number, persona, expected in _persona_rows():
        assert (
            ("“" in persona and "”" in persona)
            or number in {97, 98, 99}
        ), f"persona {number} has no quoted message or operational scenario"
        assert len(expected.split()) >= 5, f"persona {number} has no useful expected outcome"
