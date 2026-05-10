"""ND2 reader adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .base import ImageInfo, ReaderSession, _ensure_2d


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

        loop_indices = tuple(loop_indices(handle.experiment()))
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
