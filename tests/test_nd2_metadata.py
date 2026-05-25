from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from mdat.core.formats.input.nd2 import ND2ReaderAdapter


@dataclass
class _PeriodDiff:
    avg: float
    max: float = 0.0
    min: float = 0.0


@dataclass
class _TimeLoopParams:
    periodMs: float | None = None
    periodDiff: _PeriodDiff | None = None


def test_time_increment_configured_from_period_ms() -> None:
    params = _TimeLoopParams(periodMs=30000.0)

    assert ND2ReaderAdapter._time_increment_configured_s(params, 9) == 30.0


def test_time_increment_from_period_diff_avg() -> None:
    params = _TimeLoopParams(
        periodMs=30000.0,
        periodDiff=_PeriodDiff(avg=73163.444),
    )

    assert ND2ReaderAdapter._time_increment_s(params, 9) == pytest.approx(73.163444)


def test_time_increment_none_when_only_period_ms_configured() -> None:
    params = _TimeLoopParams(periodMs=5000.0)

    assert ND2ReaderAdapter._time_increment_s(params, 10) is None


def test_time_increments_none_for_single_timepoint() -> None:
    params = _TimeLoopParams(
        periodMs=30000.0,
        periodDiff=_PeriodDiff(avg=73163.444),
    )

    assert ND2ReaderAdapter._time_increment_configured_s(params, 1) is None
    assert ND2ReaderAdapter._time_increment_s(params, 1) is None


@pytest.mark.parametrize(
    ("path", "expected_configured_s", "expected_increment_s"),
    [
        (
            Path("/home/jack/data/lnp_wf/lnp_wf.nd2"),
            30.0,
            pytest.approx(73.163444),
        ),
    ],
)
def test_nd2_time_increments_on_local_files(
    path: Path,
    expected_configured_s: float,
    expected_increment_s: float,
) -> None:
    if not path.is_file():
        pytest.skip(f"Missing local fixture: {path}")

    payload = ND2ReaderAdapter().inspect_metadata(path)
    acquisition = payload.normalized["acquisition"]

    assert acquisition["time_increment_configured_s"] == expected_configured_s
    assert acquisition["time_increment_s"] == expected_increment_s
