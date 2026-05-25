from __future__ import annotations

from pathlib import Path

import pytest

from mdat.core.formats.input.czi import CZIReaderAdapter


def test_time_increment_configured_from_time_series_setup() -> None:
    adapter = CZIReaderAdapter()
    metadata = {
        "ImageDocument": {
            "Metadata": {
                "Experiment": {
                    "ExperimentBlocks": {
                        "AcquisitionBlock": {
                            "@IsActivated": "true",
                            "SubDimensionSetups": {
                                "TimeSeriesSetup": {
                                    "@IsActivated": "true",
                                    "Interval": {
                                        "TimeSpan": {
                                            "Value": "5",
                                            "DefaultUnitFormat": "s",
                                        }
                                    },
                                }
                            },
                        }
                    }
                },
                "Information": {"Image": {"Dimensions": {}}},
            }
        }
    }

    assert adapter._time_increment_configured_s(metadata, 250) == 5.0


def test_time_increment_from_t_positions_increment() -> None:
    adapter = CZIReaderAdapter()
    image = {
        "Dimensions": {
            "T": {
                "Positions": {
                    "Interval": {
                        "Start": "0",
                        "Increment": "5.000024096385542",
                    }
                }
            }
        }
    }

    assert adapter._time_increment_s(image, 250) == pytest.approx(5.000024096385542)


def test_time_increments_none_for_single_timepoint() -> None:
    adapter = CZIReaderAdapter()
    metadata = {
        "ImageDocument": {
            "Metadata": {
                "Experiment": {
                    "ExperimentBlocks": {
                        "AcquisitionBlock": {
                            "SubDimensionSetups": {
                                "TimeSeriesSetup": {
                                    "@IsActivated": "true",
                                    "Interval": {
                                        "TimeSpan": {
                                            "Value": "5",
                                            "DefaultUnitFormat": "s",
                                        }
                                    },
                                }
                            }
                        }
                    }
                },
                "Information": {"Image": {"Dimensions": {}}},
            }
        }
    }
    image = metadata["ImageDocument"]["Metadata"]["Information"]["Image"]

    assert adapter._time_increment_configured_s(metadata, 1) is None
    assert adapter._time_increment_s(image, 1) is None


@pytest.mark.parametrize(
    ("path", "expected_configured_s", "expected_increment_s"),
    [
        (
            Path("/home/jack/data/E4-OR33-LN229-KO-PeriTumorActuation-01.czi"),
            5.0,
            pytest.approx(5.000024096385542),
        ),
        (Path("/home/jack/data/airy.czi"), None, None),
    ],
)
def test_czi_time_increments_on_local_files(
    path: Path,
    expected_configured_s: float | None,
    expected_increment_s: float | None,
) -> None:
    if not path.is_file():
        pytest.skip(f"Missing local fixture: {path}")

    payload = CZIReaderAdapter().inspect_metadata(path)
    acquisition = payload.normalized["acquisition"]

    assert acquisition["time_increment_configured_s"] == expected_configured_s
    assert acquisition["time_increment_s"] == expected_increment_s
    assert "frame_interval_s" not in acquisition
    assert "frame_scan_s" not in acquisition
    assert "pixel_time_s" not in acquisition
