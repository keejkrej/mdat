"""ND2 reader adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .base import ImageInfo, MetadataPayload, ReaderSession, _ensure_2d


@dataclass(frozen=True)
class _FrameLookup:
    sequence_axes: tuple[str, ...]
    index_by_coords: dict[tuple[int, ...], int]


class ND2ReaderAdapter:
    """Adapter for ND2 files."""

    name = "nd2"
    suffixes = (".nd2",)

    def supports(self, input_path: Path) -> bool:
        return input_path.suffix.lower() in self.suffixes

    def inspect(self, input_path: Path) -> ImageInfo:
        import nd2

        handle = nd2.ND2File(str(input_path))
        try:
            sizes = handle.sizes
            return ImageInfo(
                n_pos=sizes.get("P", 1),
                n_time=sizes.get("T", 1),
                n_chan=sizes.get("C", 1),
                n_z=sizes.get("Z", 1),
            )
        finally:
            handle.close()

    @staticmethod
    def _get(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)

    @staticmethod
    def _color_hex(color: Any) -> str | None:
        if color is None:
            return None
        if hasattr(color, "as_hex"):
            return color.as_hex()
        r = getattr(color, "r", None)
        g = getattr(color, "g", None)
        b = getattr(color, "b", None)
        if all(isinstance(part, int) for part in (r, g, b)):
            return f"#{r:02x}{g:02x}{b:02x}"
        return None

    @staticmethod
    def _loop_by_type(experiment: list[Any], loop_type: str) -> Any | None:
        for loop in experiment:
            if getattr(loop, "type", None) == loop_type:
                return loop
        return None

    def _normalized_metadata(self, handle: Any) -> dict[str, Any]:
        metadata = handle.metadata
        channels_metadata = list(self._get(metadata, "channels", []))
        first_channel = channels_metadata[0] if channels_metadata else None
        first_volume = self._get(first_channel, "volume") if first_channel is not None else None
        first_microscope = (
            self._get(first_channel, "microscope") if first_channel is not None else None
        )
        sizes = dict(handle.sizes)
        attrs = handle.attributes
        experiment = list(handle.experiment)
        time_loop = self._loop_by_type(experiment, "TimeLoop")
        z_loop = self._loop_by_type(experiment, "ZStackLoop")

        axes_calibration = (
            tuple(self._get(first_volume, "axesCalibration", (None, None, None)))
            if first_volume is not None
            else (None, None, None)
        )
        channels = []
        for read_index, channel_info in enumerate(channels_metadata):
            channel = self._get(channel_info, "channel")
            microscope = self._get(channel_info, "microscope")
            volume = self._get(channel_info, "volume")
            native_index = self._get(channel, "index", read_index)
            channels.append(
                {
                    "index": read_index,
                    "id": str(native_index) if native_index is not None else None,
                    "name": self._get(channel, "name"),
                    "color": self._color_hex(self._get(channel, "color")),
                    "fluor": self._get(channel, "name"),
                    "excitation_nm": self._get(channel, "excitationLambdaNm"),
                    "emission_nm": self._get(channel, "emissionLambdaNm"),
                    "detection_range_nm": None,
                    "pixel_type": self._get(volume, "componentDataType"),
                    "acquisition_mode": None,
                    "illumination_type": (
                        ", ".join(self._get(microscope, "modalityFlags", [])) or None
                    ),
                }
            )

        time_params = getattr(time_loop, "parameters", None)
        z_params = getattr(z_loop, "parameters", None)
        text_info = handle.text_info

        return {
            "channels": channels,
            "pixel_size_um": {
                "x": axes_calibration[0],
                "y": axes_calibration[1],
                "z": axes_calibration[2],
            },
            "objective": {
                "name": self._get(first_microscope, "objectiveName"),
                "magnification": self._get(first_microscope, "objectiveMagnification"),
                "numerical_aperture": self._get(
                    first_microscope, "objectiveNumericalAperture"
                ),
                "immersion": None,
                "refractive_index": self._get(
                    first_microscope, "immersionRefractiveIndex"
                ),
            },
            "acquisition": {
                "datetime": self._get(text_info, "date"),
                "creation_datetime": None,
                "software": "NIS-Elements",
                "software_version": None,
                "microscope": None,
                "microscope_system": None,
                "frame_interval_s": (
                    getattr(time_params, "periodMs", None) / 1000
                    if getattr(time_params, "periodMs", None) is not None
                    else None
                ),
                "channel_count": len(channels),
                "primary_channel": channels[0]["name"] if channels else None,
                "z_step_um": getattr(z_params, "stepUm", None),
            },
            "dimensions": {
                "size_x": sizes.get("X") or self._get(attrs, "widthPx"),
                "size_y": sizes.get("Y") or self._get(attrs, "heightPx"),
                "size_z": sizes.get("Z", 1),
                "size_c": sizes.get("C") or self._get(attrs, "channelCount"),
                "size_t": sizes.get("T", 1),
                "size_p": sizes.get("P", 1),
                "pixel_type": self._get(attrs, "pixelDataType"),
            },
        }

    def inspect_metadata(self, input_path: Path) -> MetadataPayload:
        import nd2

        handle = nd2.ND2File(str(input_path))
        try:
            ome_metadata = handle.ome_metadata()
            raw = ome_metadata.to_xml() if hasattr(ome_metadata, "to_xml") else str(ome_metadata)

            return MetadataPayload(
                normalized=self._normalized_metadata(handle),
                raw=raw,
                raw_format="ome_xml",
            )
        finally:
            handle.close()

    def open(self, input_path: Path) -> ReaderSession:
        import nd2

        handle = nd2.ND2File(str(input_path))
        sizes = handle.sizes
        n_pos = sizes.get("P", 1)
        n_time = sizes.get("T", 1)
        n_chan = sizes.get("C", 1)
        n_z = sizes.get("Z", 1)
        frame_lookup = self._build_frame_lookup(handle)
        info = ImageInfo(n_pos=n_pos, n_time=n_time, n_chan=n_chan, n_z=n_z)

        def read_frame(p: int, t: int, c: int, z: int) -> np.ndarray:
            return self._read_frame_2d(handle, frame_lookup, p, t, c, z)

        return ReaderSession(info=info, read_frame=read_frame, close=handle.close)

    @staticmethod
    def _build_frame_lookup(handle) -> _FrameLookup:
        """Build a lookup from ND2 loop coordinates to sequence frame index."""
        from nd2._util import loop_indices

        experiment = handle.experiment() if callable(handle.experiment) else handle.experiment
        loop_indices = tuple(loop_indices(experiment))
        if not loop_indices:
            return _FrameLookup(sequence_axes=(), index_by_coords={(): 0})

        sequence_axes = tuple(
            axis
            for axis in ("P", "T", "C", "Z")
            if any(axis in frame_indices for frame_indices in loop_indices)
        )
        index_by_coords = {
            tuple(frame_indices.get(axis, 0) for axis in sequence_axes): seq_index
            for seq_index, frame_indices in enumerate(loop_indices)
        }
        return _FrameLookup(sequence_axes=sequence_axes, index_by_coords=index_by_coords)

    @staticmethod
    def _read_frame_2d(handle, lookup: _FrameLookup, p: int, t: int, c: int, z: int) -> np.ndarray:
        """Read a 2D YxX frame at the given P/T/C/Z coordinate."""
        coords = {"P": p, "T": t, "C": c, "Z": z}
        seq_key = tuple(coords[axis] for axis in lookup.sequence_axes)
        if seq_key not in lookup.index_by_coords:
            raise ValueError(
                f"No ND2 frame found for coordinates P={p}, T={t}, C={c}, Z={z}"
            )

        seq_index = lookup.index_by_coords[seq_key]
        frame = np.asarray(handle.read_frame(seq_index))

        if "C" not in lookup.sequence_axes and handle.sizes.get("C", 1) > 1:
            if frame.ndim >= 3 and frame.shape[0] == handle.sizes["C"]:
                frame = frame[c]
            elif frame.ndim >= 3 and frame.shape[-1] == handle.sizes["C"]:
                frame = frame[..., c]
            else:
                raise ValueError(
                    "Unable to locate the channel axis in ND2 frame data for in-pixel channels"
                )

        return _ensure_2d(frame)


__all__ = ["ND2ReaderAdapter"]
