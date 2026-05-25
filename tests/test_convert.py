from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from mdat.convert import (
    _acdc_basename,
    _build_channel_stack,
    _channel_for_read_index,
    _channel_labels,
    _sanitize_label,
    _write_acdc_metadata_csv,
    parse_output_format,
    position_label,
)


def test_parse_output_format() -> None:
    assert parse_output_format("mdat") == "mdat"
    assert parse_output_format("ACDC") == "acdc"
    with pytest.raises(ValueError, match="Unsupported output format"):
        parse_output_format("json")


def test_position_label() -> None:
    assert position_label(0, "mdat") == "Pos0"
    assert position_label(0, "acdc") == "Position_1"


def test_sanitize_label() -> None:
    assert _sanitize_label("GFP.channel", fallback="ch0") == "GFP_channel"
    assert _sanitize_label("  ", fallback="ch0") == "ch0"


def test_acdc_basename() -> None:
    path = Path("experiment/sample.nd2")
    assert _acdc_basename(path, 0, num_pos_digits=2) == "sample_s01_"


def test_build_channel_stack() -> None:
    calls: list[tuple[int, int, int, int]] = []

    def read_frame(p: int, t: int, c: int, z: int) -> np.ndarray:
        calls.append((p, t, c, z))
        return np.array([[p * 100 + t * 10 + c + z * 0.1]], dtype=np.uint8)

    stack = _build_channel_stack(
        read_frame,
        p_idx=2,
        time_indices=[0, 1],
        c_orig=3,
        n_z=2,
    )
    assert stack.shape == (2, 2)
    assert len(calls) == 4


def test_write_acdc_metadata_csv(tmp_path: Path) -> None:
    images_dir = tmp_path / "Position_1" / "Images"
    images_dir.mkdir(parents=True)
    csv_path = images_dir / "sample_s01_metadata.csv"
    _write_acdc_metadata_csv(
        csv_path,
        basename="sample_s01_",
        size_t=5,
        size_z=1,
        channel_indices=[0, 1],
        channel_labels={0: "GFP", 1: "phase_contrast"},
        metadata_fields={
            "lens_na": 1.4,
            "time_increment": 300.0,
            "pixel_size_x": 0.065,
            "pixel_size_y": 0.065,
            "pixel_size_z": 0.3,
        },
    )

    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))

    assert rows[0] == ["Description", "values"]
    assert ["basename", "sample_s01_"] in rows
    assert ["channel_0_name", "GFP"] in rows


def test_channel_labels_czi_incontiguous_zen_id() -> None:
    channels = [
        {
            "index": 0,
            "id": "Channel:0",
            "name": "RhodB-T1",
            "fluor": "Rhodamine B",
            "emission_nm": 565.0,
        },
        {
            "index": 1,
            "id": "Channel:2",
            "name": "AF405-T2",
            "fluor": "Alexa Fluor 405",
            "emission_nm": 422.0,
        },
    ]
    labels = _channel_labels([0, 1], channels)
    assert labels == {0: "RhodB-T1", 1: "AF405-T2"}
    assert _channel_for_read_index(channels, 1)["name"] == "AF405-T2"
