"""Tests for the eix match counter."""

from __future__ import annotations

import pytest

from carnage.core.eix.eix import count_matches


def test_counts_one_byte_per_match() -> None:
    assert count_matches(b"1111") == 4


def test_tolerates_trailing_whitespace() -> None:
    assert count_matches(b"111\n") == 3
    assert count_matches(b"") == 0


def test_unexpected_output_is_an_error_not_a_count() -> None:
    # A banner would have made len(stdout) report a plausible-looking number.
    assert count_matches(b"Found 4 matches") == -1
    assert count_matches(b"1111eix: warning") == -1


@pytest.mark.parametrize("count", [0, 1, 5, 19296])
def test_round_trip_with_a_pure_format(count: int) -> None:
    assert count_matches(b"1" * count) == count
