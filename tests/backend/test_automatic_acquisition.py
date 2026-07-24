"""Automatic production acquisition filename contract tests."""

import pytest

from backend.domain.automatic_acquisition import (
    AcquisitionFilenameError,
    AcquisitionFilenameMatcher,
)
from backend.domain.contracts import AutomaticAcquisitionConfiguration


def _matcher() -> AcquisitionFilenameMatcher:
    return AcquisitionFilenameMatcher(
        AutomaticAcquisitionConfiguration(
            filename_template="{cycle}_{position}.jpg",
            position_width=2,
            stable_for_milliseconds=1500,
            incomplete_cycle_timeout_seconds=120,
        ),
        expected_frame_count=16,
    )


def test_filename_contract_generates_matches_and_orders_exact_positions() -> None:
    matcher = _matcher()
    names = tuple(matcher.expected_filename("DISC-0042", position) for position in range(16, 0, -1))

    assert matcher.match("DISC-0042_01.jpg").cycle_id == "DISC-0042"
    assert matcher.match("DISC-0042_16.jpg").position == 16
    assert matcher.order_cycle(names) == tuple(
        f"DISC-0042_{position:02d}.jpg" for position in range(1, 17)
    )


@pytest.mark.parametrize(
    "filename",
    [
        "DISC-0042_00.jpg",
        "DISC-0042_17.jpg",
        "DISC-0042_1.jpg",
        "DISC-0042_01.png",
        "../DISC-0042_01.jpg",
    ],
)
def test_filename_contract_rejects_invalid_or_out_of_range_names(filename: str) -> None:
    with pytest.raises(AcquisitionFilenameError):
        _matcher().match(filename)


def test_cycle_order_rejects_incomplete_duplicate_and_mixed_cycles() -> None:
    matcher = _matcher()
    complete = [matcher.expected_filename("DISC-A", position) for position in range(1, 17)]

    with pytest.raises(AcquisitionFilenameError, match="incomplete"):
        matcher.order_cycle(tuple(complete[:-1]))
    with pytest.raises(AcquisitionFilenameError, match="duplicate"):
        matcher.order_cycle(tuple([*complete[:-1], complete[0]]))
    complete[-1] = matcher.expected_filename("DISC-B", 16)
    with pytest.raises(AcquisitionFilenameError, match="different cycles"):
        matcher.order_cycle(tuple(complete))
