"""Keysight HDF5 oscilloscope waveform reader."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal, Sequence


TimeAxis = Literal["relative", "x_origin", "absolute"]

_SEGMENT_DATA_RE = re.compile(r"Seg(\d+)Data$")


def read_keysight_h5(
    filename: str | Path,
    *,
    channel: str | int = "Channel 1",
    segment_numbers: Sequence[int] | None = None,
    waveform_ids: Sequence[int] | None = None,
    time_axis: TimeAxis = "relative",
    include_raw: bool = False,
) -> tuple[Any, Any, dict[str, Any]]:
    """Read selected waveform segments from a Keysight HDF5 file.

    Parameters
    ----------
    filename:
        Path to the ``.h5`` file.
    channel:
        Channel group name, for example ``"Channel 1"``, or a 1-based channel
        number.
    segment_numbers:
        1-based Keysight segment numbers to read. If omitted, all segments are
        read.
    waveform_ids:
        Optional 0-based segment positions, matching the quick helper used in
        the PMT calibration notebook. Use either ``segment_numbers`` or
        ``waveform_ids``, not both.
    time_axis:
        ``"relative"`` returns ``sample_index * XInc``. ``"x_origin"`` adds
        ``SegmentedXOrg``. ``"absolute"`` also adds ``SegmentedTimeTag``.
    include_raw:
        Include raw integer ADC arrays in ``metadata["raw"]``.

    Returns
    -------
    time:
        A one-dimensional time axis when all selected waveforms share it, or a
        two-dimensional array with shape ``(n_waveforms, n_samples)`` when each
        waveform has a distinct axis.
    voltage:
        Voltage array with shape ``(n_waveforms, n_samples)``.
    metadata:
        File, channel, and segment metadata converted to plain Python values.
    """

    _validate_time_axis(time_axis)
    h5py, np = _require_h5_modules()

    path = Path(filename)
    channel_name = _channel_name(channel)

    with h5py.File(path, "r") as h5_file:
        channel_group = h5_file["Waveforms"][channel_name]
        all_segment_names = sorted_segment_names(channel_group)
        selected_names = _select_segment_names(
            all_segment_names,
            segment_numbers=segment_numbers,
            waveform_ids=waveform_ids,
        )

        xinc = float(channel_group.attrs["XInc"])
        yinc = float(channel_group.attrs["YInc"])
        yorg = float(channel_group.attrs["YOrg"])

        time_rows = []
        voltage_rows = []
        raw_rows = []
        selected_segments = []
        time_tags = []
        x_origins = []
        segment_attrs = {}

        for name in selected_names:
            dataset = channel_group[name]
            raw = dataset[()]
            relative_time = np.arange(raw.size, dtype=float) * xinc

            time_tag = float(dataset.attrs.get("SegmentedTimeTag", 0.0))
            x_origin = float(dataset.attrs.get("SegmentedXOrg", channel_group.attrs["XOrg"]))
            time = _build_time_axis(
                relative_time,
                time_axis=time_axis,
                time_tag=time_tag,
                x_origin=x_origin,
            )

            segment = segment_number(name)
            selected_segments.append(segment)
            time_tags.append(time_tag)
            x_origins.append(x_origin)
            segment_attrs[segment] = attrs_to_dict(dataset)
            time_rows.append(time)
            voltage_rows.append(raw.astype(float) * yinc + yorg)
            if include_raw:
                raw_rows.append(raw)

        voltage = np.vstack(voltage_rows)
        time = _collapse_time_rows(time_rows, np)

        metadata = {
            "file_type": _read_dataset(h5_file, "FileType/KeysightH5FileType"),
            "frame": _read_dataset(h5_file, "Frame/TheFrame"),
            "channel": channel_name,
            "channel_attrs": attrs_to_dict(channel_group),
            "segment_numbers": selected_segments,
            "time_tags": np.array(time_tags),
            "x_origins": np.array(x_origins),
            "segment_attrs": segment_attrs,
        }
        if include_raw:
            metadata["raw"] = np.vstack(raw_rows)

    return time, voltage, metadata


def read_oscilloscope_h5(*args: Any, **kwargs: Any) -> tuple[Any, Any, dict[str, Any]]:
    """Alias for :func:`read_keysight_h5`."""

    return read_keysight_h5(*args, **kwargs)


def read_segment_time_tags(
    filename: str | Path,
    *,
    channel: str | int = "Channel 1",
) -> tuple[Any, Any]:
    """Read segment numbers and ``SegmentedTimeTag`` values without waveforms."""

    h5py, np = _require_h5_modules()
    channel_name = _channel_name(channel)

    with h5py.File(filename, "r") as h5_file:
        channel_group = h5_file["Waveforms"][channel_name]
        names = sorted_segment_names(channel_group)
        segments = np.array([segment_number(name) for name in names], dtype=int)
        tags = np.array(
            [float(channel_group[name].attrs["SegmentedTimeTag"]) for name in names],
            dtype=float,
        )

    return segments, tags


def segment_number(name: str) -> int:
    """Extract the integer segment number from names like ``Channel 1 Seg12Data``."""

    match = _SEGMENT_DATA_RE.search(name)
    if not match:
        raise ValueError(f"Could not extract a segment number from {name!r}")
    return int(match.group(1))


def sorted_segment_names(channel_group: Any) -> list[str]:
    """Return waveform dataset names sorted by numeric segment number."""

    names = [name for name in channel_group.keys() if _SEGMENT_DATA_RE.search(name)]
    return sorted(names, key=segment_number)


def attrs_to_dict(h5_object: Any) -> dict[str, Any]:
    """Return HDF5 attributes as plain Python values."""

    return {key: decode_h5_value(h5_object.attrs[key]) for key in h5_object.attrs.keys()}


def decode_h5_value(value: Any) -> Any:
    """Convert common HDF5/numpy values into plain Python values."""

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    dtype = getattr(value, "dtype", None)
    dtype_names = getattr(dtype, "names", None)
    if dtype_names:
        return {name: decode_h5_value(value[name]) for name in dtype_names}

    shape = getattr(value, "shape", None)
    if shape is not None and hasattr(value, "tolist"):
        if shape == ():
            return decode_h5_value(value.item())
        if getattr(dtype, "kind", None) == "S":
            return [decode_h5_value(item) for item in value.tolist()]
        return value.tolist()

    if hasattr(value, "item"):
        try:
            return decode_h5_value(value.item())
        except (TypeError, ValueError):
            pass

    return value


def _require_h5_modules() -> tuple[Any, Any]:
    try:
        import h5py
        import numpy as np
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Reading Keysight HDF5 oscilloscope files requires h5py and numpy. "
            "Install Lab-tools with its project dependencies first."
        ) from exc

    return h5py, np


def _channel_name(channel: str | int) -> str:
    if isinstance(channel, int):
        if channel < 1:
            raise ValueError("channel numbers are 1-based")
        return f"Channel {channel}"
    return channel


def _select_segment_names(
    segment_names: Sequence[str],
    *,
    segment_numbers: Sequence[int] | None,
    waveform_ids: Sequence[int] | None,
) -> list[str]:
    if segment_numbers is not None and waveform_ids is not None:
        raise ValueError("Use either segment_numbers or waveform_ids, not both")

    if waveform_ids is not None:
        selected = []
        for waveform_id in waveform_ids:
            index = int(waveform_id)
            if index < 0 or index >= len(segment_names):
                raise ValueError(f"waveform id {waveform_id} is out of range")
            selected.append(segment_names[index])
        return selected

    if segment_numbers is None:
        return list(segment_names)

    names_by_number = {segment_number(name): name for name in segment_names}
    selected_numbers = [int(segment) for segment in segment_numbers]
    missing = [segment for segment in selected_numbers if segment not in names_by_number]
    if missing:
        raise ValueError(f"segments {missing} were not found in the HDF5 channel")

    return [names_by_number[segment] for segment in selected_numbers]


def _validate_time_axis(time_axis: str) -> None:
    if time_axis not in {"relative", "x_origin", "absolute"}:
        raise ValueError("time_axis must be 'relative', 'x_origin', or 'absolute'")


def _build_time_axis(
    relative_time: Any,
    *,
    time_axis: TimeAxis,
    time_tag: float,
    x_origin: float,
) -> Any:
    if time_axis == "relative":
        return relative_time
    if time_axis == "x_origin":
        return relative_time + x_origin
    return relative_time + x_origin + time_tag


def _collapse_time_rows(time_rows: Sequence[Any], np: Any) -> Any:
    if len(time_rows) == 1:
        return time_rows[0]
    if all(np.array_equal(time_rows[0], other) for other in time_rows[1:]):
        return time_rows[0]
    return np.vstack(time_rows)


def _read_dataset(h5_file: Any, path: str) -> Any:
    if path not in h5_file:
        return None
    return decode_h5_value(h5_file[path][()])
