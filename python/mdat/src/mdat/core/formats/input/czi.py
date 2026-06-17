"""CZI reader adapter."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from mdat.core.io.sources import InputLocation, open_binary_source

from .base import ImageInfo, MetadataPayload, ReaderSession, _ensure_2d


def _open_czi_context(input_path: InputLocation):
    from pylibCZIrw import czi as pyczi

    source = open_binary_source(input_path)
    if isinstance(source, Path):
        return pyczi.open_czi(str(source))
    return pyczi.open_czi(source)


class CZIReaderAdapter:
    """Adapter for CZI files."""

    name = "czi"
    suffixes = (".czi",)

    def supports(self, input_path: InputLocation) -> bool:
        from mdat.core.io.sources import location_suffix

        return location_suffix(input_path) in self.suffixes

    @staticmethod
    def _axis_size(ranges: Mapping[str, tuple[int, int]], axis: str) -> int:
        start, stop = ranges.get(axis, (0, 1))
        if start < 0 or stop < start:
            raise ValueError(f"Invalid bounding range for axis {axis}: {(start, stop)!r}")
        return stop - start

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _timespan_to_seconds(timespan: Mapping[str, Any] | None) -> float | None:
        if not isinstance(timespan, Mapping):
            return None
        value = CZIReaderAdapter._safe_float(timespan.get("Value"))
        if value is None:
            return None
        unit = str(timespan.get("DefaultUnitFormat", "s")).lower()
        if unit in {"s", "sec", "second", "seconds"}:
            return value
        if unit in {"ms", "millisecond", "milliseconds"}:
            return value / 1000
        if unit in {"us", "µs", "microsecond", "microseconds"}:
            return value / 1_000_000
        if unit in {"min", "minute", "minutes"}:
            return value * 60
        if unit in {"h", "hour", "hours"}:
            return value * 3600
        return value

    @staticmethod
    def _iter_acquisition_blocks(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        image_document = metadata.get("ImageDocument", {})
        md = image_document.get("Metadata", {}) if isinstance(image_document, Mapping) else {}
        experiment = md.get("Experiment", {}) if isinstance(md, Mapping) else {}
        blocks = experiment.get("ExperimentBlocks", {}) if isinstance(experiment, Mapping) else {}
        acquisition_blocks = (
            blocks.get("AcquisitionBlock", []) if isinstance(blocks, Mapping) else []
        )
        return [
            block
            for block in CZIReaderAdapter._as_list(acquisition_blocks)
            if isinstance(block, Mapping)
        ]

    def _time_increment_configured_s(
        self,
        metadata: Mapping[str, Any],
        size_t: int,
    ) -> float | None:
        """Return the configured interval between consecutive T frames in seconds."""
        if size_t <= 1:
            return None

        for block in self._iter_acquisition_blocks(metadata):
            setups = block.get("SubDimensionSetups", {})
            if not isinstance(setups, Mapping):
                continue
            time_series = setups.get("TimeSeriesSetup", {})
            if not isinstance(time_series, Mapping):
                continue
            if str(time_series.get("@IsActivated", "")).lower() != "true":
                continue
            interval = time_series.get("Interval", {})
            if not isinstance(interval, Mapping):
                continue
            seconds = self._timespan_to_seconds(interval.get("TimeSpan"))
            if seconds is not None and seconds > 0:
                return seconds

        return None

    def _time_increment_s(
        self,
        image: Mapping[str, Any],
        size_t: int,
    ) -> float | None:
        """Return the measured interval between consecutive T frames in seconds."""
        if size_t <= 1:
            return None

        dimensions = image.get("Dimensions", {}) if isinstance(image.get("Dimensions"), Mapping) else {}
        t_dimension = dimensions.get("T", {})
        if isinstance(t_dimension, Mapping):
            positions = t_dimension.get("Positions", {})
            if isinstance(positions, Mapping):
                interval = positions.get("Interval", {})
                if isinstance(interval, Mapping):
                    increment = self._safe_float(interval.get("Increment"))
                    if increment is not None and increment > 0:
                        return increment

        return None

    def _normalized_metadata(
        self,
        metadata: Mapping[str, Any],
        total_bounding_box: Mapping[str, tuple[int, int]],
        scenes_bounding_rectangle: Mapping[Any, Any],
        pixel_types: Mapping[Any, Any],
    ) -> dict[str, Any]:
        image_document = metadata.get("ImageDocument", {})
        md = image_document.get("Metadata", {}) if isinstance(image_document, Mapping) else {}
        information = md.get("Information", {}) if isinstance(md, Mapping) else {}
        image = information.get("Image", {}) if isinstance(information, Mapping) else {}
        instrument = information.get("Instrument", {}) if isinstance(information, Mapping) else {}
        application = information.get("Application", {}) if isinstance(information, Mapping) else {}
        document = information.get("Document", {}) if isinstance(information, Mapping) else {}

        scaling = md.get("Scaling", {}) if isinstance(md, Mapping) else {}
        distances = (
            scaling.get("Items", {}).get("Distance", [])
            if isinstance(scaling.get("Items"), Mapping)
            else []
        )
        pixel_size_um: dict[str, float | None] = {"x": None, "y": None, "z": None}
        for distance in self._as_list(distances):
            if not isinstance(distance, Mapping):
                continue
            axis = str(distance.get("@Id", "")).lower()
            if axis in pixel_size_um:
                value_m = self._safe_float(distance.get("Value"))
                pixel_size_um[axis] = value_m * 1_000_000 if value_m is not None else None

        display = md.get("DisplaySetting", {}) if isinstance(md, Mapping) else {}
        display_channels = (
            display.get("Channels", {}).get("Channel", [])
            if isinstance(display.get("Channels"), Mapping)
            else []
        )
        display_by_id = {
            item.get("@Id"): item
            for item in self._as_list(display_channels)
            if isinstance(item, Mapping)
        }

        image_dimensions = image.get("Dimensions", {}) if isinstance(image.get("Dimensions"), Mapping) else {}
        image_channels = (
            image_dimensions.get("Channels", {}).get("Channel", [])
            if isinstance(image_dimensions.get("Channels"), Mapping)
            else []
        )
        channels = []
        for read_index, channel in enumerate(self._as_list(image_channels)):
            if not isinstance(channel, Mapping):
                continue
            display_channel = display_by_id.get(channel.get("@Id"), {})
            channels.append(
                {
                    "index": read_index,
                    "id": channel.get("@Id"),
                    "name": channel.get("@Name") or display_channel.get("@Name"),
                    "color": channel.get("Color") or display_channel.get("Color"),
                    "fluor": channel.get("Fluor") or display_channel.get("DyeName"),
                    "excitation_nm": self._safe_float(channel.get("ExcitationWavelength")),
                    "emission_nm": self._safe_float(channel.get("EmissionWavelength")),
                    "detection_range_nm": (
                        channel.get("DetectionWavelength", {}).get("Ranges")
                        if isinstance(channel.get("DetectionWavelength"), Mapping)
                        else None
                    ),
                    "pixel_type": channel.get("PixelType") or pixel_types.get(read_index),
                    "acquisition_mode": channel.get("AcquisitionMode"),
                    "illumination_type": channel.get("IlluminationType"),
                }
            )

        objectives = instrument.get("Objectives", {}) if isinstance(instrument.get("Objectives"), Mapping) else {}
        objective = objectives.get("Objective", {}) if isinstance(objectives, Mapping) else {}
        if isinstance(objective, list):
            objective = objective[0] if objective else {}

        microscope_settings = image.get("ObjectiveSettings", {}) if isinstance(image.get("ObjectiveSettings"), Mapping) else {}
        microscope = instrument.get("Microscopes", {}) if isinstance(instrument.get("Microscopes"), Mapping) else {}
        microscope_item = microscope.get("Microscope", {}) if isinstance(microscope, Mapping) else {}

        first_channel = channels[0] if channels else {}

        size_t = (
            self._safe_int(image.get("SizeT"))
            or self._axis_size(total_bounding_box, "T")
        )

        return {
            "channels": channels,
            "pixel_size_um": pixel_size_um,
            "objective": {
                "name": objective.get("@Name"),
                "magnification": self._safe_float(objective.get("NominalMagnification")),
                "numerical_aperture": self._safe_float(objective.get("LensNA")),
                "immersion": objective.get("Immersion") or microscope_settings.get("Medium"),
                "refractive_index": self._safe_float(
                    objective.get("ImmersionRefractiveIndex")
                    or microscope_settings.get("RefractiveIndex")
                ),
            },
            "acquisition": {
                "datetime": image.get("AcquisitionDateAndTime"),
                "creation_datetime": document.get("CreationDate"),
                "software": application.get("Name"),
                "software_version": application.get("Version"),
                "microscope": microscope_item.get("@Name"),
                "microscope_system": microscope_item.get("System"),
                "time_increment_configured_s": self._time_increment_configured_s(
                    metadata, size_t
                ),
                "time_increment_s": self._time_increment_s(image, size_t),
                "channel_count": len(channels),
                "primary_channel": first_channel.get("name"),
            },
            "dimensions": {
                "size_x": self._safe_int(image.get("SizeX"))
                or self._axis_size(total_bounding_box, "X"),
                "size_y": self._safe_int(image.get("SizeY"))
                or self._axis_size(total_bounding_box, "Y"),
                "size_z": self._safe_int(image.get("SizeZ"))
                or self._axis_size(total_bounding_box, "Z"),
                "size_c": self._safe_int(image.get("SizeC"))
                or self._axis_size(total_bounding_box, "C"),
                "size_t": size_t,
                "size_p": len(scenes_bounding_rectangle) if scenes_bounding_rectangle else 1,
                "pixel_type": image.get("PixelType"),
            },
        }

    def inspect(self, input_path: InputLocation) -> ImageInfo:
        with _open_czi_context(input_path) as handle:
            total_bounding_box = dict(handle.total_bounding_box)
            scenes_bounding = dict(handle.scenes_bounding_rectangle)
            has_scenes = len(scenes_bounding) > 0
            n_pos = len(scenes_bounding) if has_scenes else 1

            return ImageInfo(
                n_pos=n_pos,
                n_time=self._axis_size(total_bounding_box, "T"),
                n_chan=self._axis_size(total_bounding_box, "C"),
                n_z=self._axis_size(total_bounding_box, "Z"),
            )

    def inspect_metadata(self, input_path: InputLocation) -> MetadataPayload:
        with _open_czi_context(input_path) as handle:
            total_bounding_box = handle.total_bounding_box
            scenes_bounding_rectangle = handle.scenes_bounding_rectangle
            pixel_types = handle.pixel_types
            return MetadataPayload(
                normalized=self._normalized_metadata(
                    handle.metadata,
                    total_bounding_box,
                    scenes_bounding_rectangle,
                    pixel_types,
                ),
                raw=handle.raw_metadata,
                raw_format="xml",
            )

    def open(self, input_path: InputLocation) -> ReaderSession:
        cm = _open_czi_context(input_path)
        handle = cm.__enter__()
        total_bounding_box = handle.total_bounding_box
        scenes_bounding = handle.scenes_bounding_rectangle
        has_scenes = len(scenes_bounding) > 0
        scene_ids: list[object] = list(scenes_bounding) if has_scenes else []
        n_pos = len(scene_ids) if has_scenes else 1
        n_time = self._axis_size(total_bounding_box, "T")
        n_chan = self._axis_size(total_bounding_box, "C")
        n_z = self._axis_size(total_bounding_box, "Z")
        include_channel = n_chan > 1
        info = ImageInfo(n_pos=n_pos, n_time=n_time, n_chan=n_chan, n_z=n_z)
        scene_ids_tuple = tuple(scene_ids)

        def read_frame(p: int, t: int, c: int, z: int) -> np.ndarray:
            plane: dict[str, int] = {"T": t, "Z": z}
            if include_channel:
                plane["C"] = c
            kwargs: dict[str, object] = {"plane": plane}
            if scene_ids:
                kwargs["scene"] = scene_ids_tuple[p]
            return _ensure_2d(np.asarray(handle.read(**kwargs)))

        def close() -> None:
            close_method = getattr(cm, "__exit__", None)
            if callable(close_method):
                close_method(None, None, None)
            else:
                raise ValueError("Unable to close CZI handle correctly")

        return ReaderSession(info=info, read_frame=read_frame, close=close)


__all__ = ["CZIReaderAdapter"]
