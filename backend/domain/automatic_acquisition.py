"""Deterministic filename matching for automatic production acquisition."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.domain.contracts import AutomaticAcquisitionConfiguration

_CYCLE_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"


class AcquisitionFilenameError(ValueError):
    """Raised when a production filename violates the configured contract."""


@dataclass(frozen=True, slots=True)
class MatchedAcquisitionFrame:
    cycle_id: str
    position: int
    filename: str


class AcquisitionFilenameMatcher:
    def __init__(
        self,
        configuration: AutomaticAcquisitionConfiguration,
        *,
        expected_frame_count: int,
    ) -> None:
        self._configuration = configuration
        self._expected_frame_count = expected_frame_count
        escaped = re.escape(configuration.filename_template)
        escaped = escaped.replace(
            re.escape("{cycle}"),
            f"(?P<cycle>{_CYCLE_PATTERN})",
        )
        escaped = escaped.replace(
            re.escape("{position}"),
            f"(?P<position>[0-9]{{{configuration.position_width}}})",
        )
        self._pattern = re.compile(f"^{escaped}$", re.IGNORECASE)

    def match(self, filename: str) -> MatchedAcquisitionFrame:
        if "/" in filename or "\\" in filename:
            raise AcquisitionFilenameError("acquisition name must be a filename")
        result = self._pattern.fullmatch(filename)
        if result is None:
            raise AcquisitionFilenameError("filename does not match the pipeline template")
        position = int(result.group("position"))
        if not 1 <= position <= self._expected_frame_count:
            raise AcquisitionFilenameError("filename position is outside the expected cycle")
        return MatchedAcquisitionFrame(
            cycle_id=result.group("cycle"),
            position=position,
            filename=filename,
        )

    def expected_filename(self, cycle_id: str, position: int) -> str:
        if re.fullmatch(_CYCLE_PATTERN, cycle_id) is None:
            raise AcquisitionFilenameError("cycle identifier is invalid")
        if not 1 <= position <= self._expected_frame_count:
            raise AcquisitionFilenameError("position is outside the expected cycle")
        return self._configuration.filename_template.replace(
            "{cycle}",
            cycle_id,
        ).replace(
            "{position}",
            str(position).zfill(self._configuration.position_width),
        )

    def order_cycle(self, filenames: tuple[str, ...]) -> tuple[str, ...]:
        positions: dict[int, str] = {}
        cycle_id: str | None = None
        for filename in filenames:
            matched = self.match(filename)
            if cycle_id is None:
                cycle_id = matched.cycle_id
            elif matched.cycle_id.casefold() != cycle_id.casefold():
                raise AcquisitionFilenameError("filenames belong to different cycles")
            if matched.position in positions:
                raise AcquisitionFilenameError("cycle contains a duplicate position")
            positions[matched.position] = filename
        expected = set(range(1, self._expected_frame_count + 1))
        if set(positions) != expected:
            raise AcquisitionFilenameError("cycle is incomplete")
        return tuple(positions[position] for position in sorted(positions))
