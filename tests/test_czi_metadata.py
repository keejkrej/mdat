from __future__ import annotations

from pathlib import Path

import pytest

from mdat.core.formats.input.czi import CZIReaderAdapter


def test_timelapse_interval_from_active_time_series_setup() -> None:
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

    assert adapter._timelapse_interval_s(metadata, metadata["ImageDocument"]["Metadata"]["Information"]["Image"], 250) == 5.0


def test_timelapse_interval_from_t_positions_increment() -> None:
    adapter = CZIReaderAdapter()
    metadata = {"ImageDocument": {"Metadata": {"Experiment": {"ExperimentBlocks": {}}}}}
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

    assert adapter._timelapse_interval_s(metadata, image, 250) == pytest.approx(5.000024096385542)


def test_timelapse_interval_none_for_single_timepoint() -> None:
    adapter = CZIReaderAdapter()
    metadata = {
        "ImageDocument": {
            "Metadata": {
                "Experiment": {
                    "ExperimentBlocks": {
                        "AcquisitionBlock": {
                            "SubDimensionSetups": {
                                "TimeSeriesSetup": {
                                    "@IsActivated": "false",
                                    "Interval": {
                                        "TimeSpan": {
                                            "Value": "0",
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

    assert adapter._timelapse_interval_s(metadata, metadata["ImageDocument"]["Metadata"]["Information"]["Image"], 1) is None


@pytest.mark.parametrize(
    ("path", "expected_frame_interval_s"),
    [
        (Path("/home/jack/data/E4-OR33-LN229-KO-PeriTumorActuation-01.czi"), 5.0),
        (Path("/home/jack/data/airy.czi"), None),
    ],
)
def test_czi_frame_interval_on_local_files(
    path: Path,
    expected_frame_interval_s: float | None,
) -> None:
    if not path.is_file():
        pytest.skip(f"Missing local fixture: {path}")

    payload = CZIReaderAdapter().inspect_metadata(path)
    acquisition = payload.normalized["acquisition"]

    assert acquisition["frame_interval_s"] == expected_frame_interval_s
    assert "frame_scan_s" not in acquisition
    assert "pixel_time_s" not in acquisition
