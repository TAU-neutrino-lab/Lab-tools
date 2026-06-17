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
        channel_group = keysight_channel_group(h5_file, channel_name)
        time, voltage, metadata = _read_keysight_channel(
            h5_file,
            channel_group,
            channel_name=channel_name,
            segment_numbers=segment_numbers,
            waveform_ids=waveform_ids,
            time_axis=time_axis,
            include_raw=include_raw,
            dtype=float,
        )

    return time, voltage, metadata


def read_keysight_h5_direct(
    filename: str | Path,
    *,
    channel: str | int = "Channel 1",
    segment_numbers: Sequence[int] | None = None,
    dtype: Any = None,
) -> tuple[Any, Any, dict[str, Any]]:
    """Compatibility reader for PMT notebooks.

    Returns time in seconds and voltage in volts. For waveform-table exports,
    ``segment_numbers`` are interpreted as 0-based row indices, matching the
    previous PMT helper.
    """

    h5py, np = _require_h5_modules()
    if dtype is None:
        dtype = np.float32

    path = Path(filename)
    channel_name = _channel_name(channel)
    with h5py.File(path, "r") as h5_file:
        channel_group = keysight_channel_group(h5_file, channel_name)
        time, voltage, metadata = _read_keysight_channel(
            h5_file,
            channel_group,
            channel_name=channel_name,
            segment_numbers=segment_numbers,
            waveform_ids=None,
            time_axis="x_origin",
            include_raw=False,
            dtype=dtype,
            table_segment_numbers_are_rows=True,
        )
        time = keysight_time_axis(channel_group, np=np, time_axis="x_origin")

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
        channel_group = keysight_channel_group(h5_file, channel_name)
        names = sorted_segment_names(channel_group) or _single_unsegmented_waveform_name(channel_group)
        if not names:
            available = ", ".join(channel_group.keys()) or "<empty>"
            raise ValueError(
                f"No waveform datasets were found in {channel_group.name!r}. "
                f"Available entries: {available}"
            )
        segments = np.array(
            [segment_number(name, default=index + 1) for index, name in enumerate(names)],
            dtype=int,
        )
        tags = np.array(
            [float(channel_group[name].attrs.get("SegmentedTimeTag", 0.0)) for name in names],
            dtype=float,
        )

    return segments, tags


def iter_keysight_chunks(
    files: Sequence[str | Path],
    *,
    channel: str | int = "Channel 1",
    chunk_size: int = 512,
    dtype: Any = None,
):
    """Yield waveform chunks in mV for one or more Keysight HDF5 files."""

    h5py, np = _require_h5_modules()
    if dtype is None:
        dtype = np.float32

    channel_name = _channel_name(channel)
    reference_len = None

    for filename in files:
        path = Path(filename)
        with h5py.File(path, "r") as h5_file:
            channel_group = keysight_channel_group(h5_file, channel_name)
            attrs = channel_group.attrs
            time_ns = keysight_time_axis(channel_group, np=np, time_axis="x_origin") * 1e9

            if reference_len is None:
                reference_len = len(time_ns)
            elif len(time_ns) != reference_len:
                raise ValueError(f"Time axes have different lengths in {path}")

            yinc_mV = float(attrs["YInc"]) * 1e3
            yorg_mV = float(attrs["YOrg"]) * 1e3
            names = sorted_segment_names(channel_group)
            waveform_dataset = keysight_waveform_dataset(channel_group, channel_name)

            if names:
                for start in range(0, len(names), chunk_size):
                    chunk_names = names[start : start + chunk_size]
                    raw = np.stack([channel_group[name][()] for name in chunk_names]).astype(dtype, copy=False)
                    yield {
                        "filename": str(path),
                        "time_ns": time_ns,
                        "voltage_mV": raw * yinc_mV + yorg_mV,
                        "segment_numbers": [
                            segment_number(name, default=index + 1)
                            for index, name in enumerate(chunk_names, start=start)
                        ],
                        "metadata": _keysight_metadata(
                            h5_file,
                            channel_group,
                            channel_name=channel_name,
                            segment_numbers=[],
                            layout="segment_datasets",
                        ),
                    }
            elif waveform_dataset is not None:
                n_samples = int(attrs["NumPoints"])
                n_waveforms = keysight_waveform_count(channel_group, waveform_dataset)
                for start in range(0, n_waveforms, chunk_size):
                    stop = min(start + chunk_size, n_waveforms)
                    raw = read_keysight_waveform_rows(waveform_dataset, start, stop, n_samples, dtype=dtype)
                    yield {
                        "filename": str(path),
                        "time_ns": time_ns,
                        "voltage_mV": raw * yinc_mV + yorg_mV,
                        "segment_numbers": list(range(start, stop)),
                        "metadata": _keysight_metadata(
                            h5_file,
                            channel_group,
                            channel_name=channel_name,
                            segment_numbers=[],
                            layout="waveform_dataset",
                        ),
                    }
            else:
                raise _no_waveforms_error(channel_group)


def standard_units(time: Any, voltage: Any, metadata: dict[str, Any]) -> tuple[Any, Any, float, str, str]:
    """Convert Keysight seconds/volts reader output to ns/mV."""

    _h5py, np = _require_h5_modules()
    time_ns = np.asarray(time) * 1e9
    voltage_mV = np.asarray(voltage) * 1e3
    adc_step_mV = float(metadata["channel_attrs"]["YInc"]) * 1e3
    return time_ns, voltage_mV, adc_step_mV, "ns", "mV"


def segment_number(name: str, *, default: int | None = None) -> int:
    """Extract the integer segment number from names like ``Channel 1 Seg12Data``."""

    match = _SEGMENT_DATA_RE.search(name)
    if not match:
        if default is not None:
            return default
        raise ValueError(f"Could not extract a segment number from {name!r}")
    return int(match.group(1))


def keysight_channel_group(h5_file: Any, channel: str | int = "Channel 1") -> Any:
    """Return a Keysight channel group from either common HDF5 layout."""

    channel_name = _channel_name(channel)
    if channel_name in h5_file:
        return h5_file[channel_name]
    if "Waveforms" in h5_file and channel_name in h5_file["Waveforms"]:
        return h5_file["Waveforms"][channel_name]
    raise KeyError(f"Could not find {channel_name!r} in {h5_file.filename}")


def keysight_waveform_dataset(channel_group: Any, channel: str | int = "Channel 1") -> Any | None:
    """Return a single waveform-table dataset, if this channel uses one."""

    h5py, _np = _require_h5_modules()
    channel_name = _channel_name(channel)
    data_name = f"{channel_name}Data"
    if data_name in channel_group:
        return channel_group[data_name]

    dataset_names = [
        name
        for name, value in channel_group.items()
        if isinstance(value, h5py.Dataset)
        and name.endswith("Data")
        and not _SEGMENT_DATA_RE.search(name)
    ]
    if len(dataset_names) == 1:
        return channel_group[dataset_names[0]]
    return None


def keysight_waveform_count(channel_group: Any, waveform_dataset: Any | None = None) -> int:
    """Return the number of waveforms stored in a Keysight channel group."""

    attrs = channel_group.attrs
    if "NumWaveforms" in attrs:
        return int(attrs["NumWaveforms"])
    if "NumSegments" in attrs and int(attrs["NumSegments"]) > 0:
        return int(attrs["NumSegments"])
    if waveform_dataset is not None:
        n_samples = int(attrs["NumPoints"])
        shape = waveform_dataset.shape
        if len(shape) == 2:
            return int(shape[0] if shape[1] == n_samples else shape[1])
        if len(shape) == 1:
            return int(shape[0] // n_samples)
    return len(sorted_segment_names(channel_group))


def keysight_time_axis(channel_group: Any, *, np: Any | None = None, time_axis: TimeAxis = "relative") -> Any:
    """Return the channel-level time axis in seconds."""

    _validate_time_axis(time_axis)
    if np is None:
        _h5py, np = _require_h5_modules()

    attrs = channel_group.attrs
    n_samples = int(attrs["NumPoints"])
    relative_time = np.arange(n_samples, dtype=float) * float(attrs["XInc"])
    return _build_time_axis(
        relative_time,
        time_axis=time_axis,
        time_tag=0.0,
        x_origin=float(attrs.get("XOrg", 0.0)),
    )


def read_keysight_waveform_rows(
    waveform_dataset: Any,
    start: int,
    stop: int,
    n_samples: int,
    *,
    dtype: Any = None,
) -> Any:
    """Read rows from a Keysight waveform-table dataset as ``(events, samples)``."""

    _h5py, np = _require_h5_modules()
    if dtype is None:
        dtype = np.float32

    shape = waveform_dataset.shape
    if len(shape) == 2:
        if shape[1] == n_samples:
            return waveform_dataset[start:stop, :].astype(dtype, copy=False)
        if shape[0] == n_samples:
            return waveform_dataset[:, start:stop].T.astype(dtype, copy=False)
        raise ValueError(f"Cannot infer waveform axis from dataset shape {shape} and NumPoints={n_samples}")

    if len(shape) == 1:
        raw = waveform_dataset[start * n_samples : stop * n_samples]
        return raw.reshape(stop - start, n_samples).astype(dtype, copy=False)

    raise ValueError(f"Unsupported Keysight waveform dataset shape {shape}")


def sorted_segment_names(channel_group: Any) -> list[str]:
    """Return waveform dataset names sorted by numeric segment number."""

    names = [name for name in channel_group.keys() if _SEGMENT_DATA_RE.search(name)]
    return sorted(names, key=segment_number)


def _single_unsegmented_waveform_name(channel_group: Any) -> list[str]:
    """Return a fallback waveform dataset for unsegmented Keysight exports."""

    candidates = []
    for name, obj in channel_group.items():
        shape = getattr(obj, "shape", None)
        dtype = getattr(obj, "dtype", None)
        if shape is None or dtype is None:
            continue
        if len(shape) == 1 and getattr(dtype, "kind", None) in "biufc":
            candidates.append(name)

    if len(candidates) == 1:
        return candidates
    return []


def _read_keysight_channel(
    h5_file: Any,
    channel_group: Any,
    *,
    channel_name: str,
    segment_numbers: Sequence[int] | None,
    waveform_ids: Sequence[int] | None,
    time_axis: TimeAxis,
    include_raw: bool,
    dtype: Any,
    table_segment_numbers_are_rows: bool = False,
) -> tuple[Any, Any, dict[str, Any]]:
    _h5py, np = _require_h5_modules()
    names = sorted_segment_names(channel_group)
    waveform_dataset = keysight_waveform_dataset(channel_group, channel_name)

    if names:
        return _read_segment_datasets(
            h5_file,
            channel_group,
            names,
            channel_name=channel_name,
            segment_numbers=segment_numbers,
            waveform_ids=waveform_ids,
            time_axis=time_axis,
            include_raw=include_raw,
            dtype=dtype,
            np=np,
        )

    if waveform_dataset is not None:
        return _read_waveform_table(
            h5_file,
            channel_group,
            waveform_dataset,
            channel_name=channel_name,
            segment_numbers=segment_numbers,
            waveform_ids=waveform_ids,
            time_axis=time_axis,
            include_raw=include_raw,
            dtype=dtype,
            np=np,
            table_segment_numbers_are_rows=table_segment_numbers_are_rows,
        )

    single_names = _single_unsegmented_waveform_name(channel_group)
    if single_names:
        return _read_segment_datasets(
            h5_file,
            channel_group,
            single_names,
            channel_name=channel_name,
            segment_numbers=segment_numbers,
            waveform_ids=waveform_ids,
            time_axis=time_axis,
            include_raw=include_raw,
            dtype=dtype,
            np=np,
        )

    raise _no_waveforms_error(channel_group)


def _read_segment_datasets(
    h5_file: Any,
    channel_group: Any,
    names: Sequence[str],
    *,
    channel_name: str,
    segment_numbers: Sequence[int] | None,
    waveform_ids: Sequence[int] | None,
    time_axis: TimeAxis,
    include_raw: bool,
    dtype: Any,
    np: Any,
) -> tuple[Any, Any, dict[str, Any]]:
    selected_names = _select_segment_names(
        names,
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
        x_origin = float(dataset.attrs.get("SegmentedXOrg", channel_group.attrs.get("XOrg", 0.0)))
        time = _build_time_axis(
            relative_time,
            time_axis=time_axis,
            time_tag=time_tag,
            x_origin=x_origin,
        )

        segment = segment_number(name, default=len(selected_segments) + 1)
        selected_segments.append(segment)
        time_tags.append(time_tag)
        x_origins.append(x_origin)
        segment_attrs[segment] = attrs_to_dict(dataset)
        time_rows.append(time)
        voltage_rows.append(raw.astype(dtype, copy=False) * yinc + yorg)
        if include_raw:
            raw_rows.append(raw)

    voltage = np.vstack(voltage_rows)
    time = _collapse_time_rows(time_rows, np)
    metadata = _keysight_metadata(
        h5_file,
        channel_group,
        channel_name=channel_name,
        segment_numbers=selected_segments,
        layout="segment_datasets",
    )
    metadata["time_tags"] = np.array(time_tags)
    metadata["x_origins"] = np.array(x_origins)
    metadata["segment_attrs"] = segment_attrs
    if include_raw:
        metadata["raw"] = np.vstack(raw_rows)

    return time, voltage, metadata


def _read_waveform_table(
    h5_file: Any,
    channel_group: Any,
    waveform_dataset: Any,
    *,
    channel_name: str,
    segment_numbers: Sequence[int] | None,
    waveform_ids: Sequence[int] | None,
    time_axis: TimeAxis,
    include_raw: bool,
    dtype: Any,
    np: Any,
    table_segment_numbers_are_rows: bool,
) -> tuple[Any, Any, dict[str, Any]]:
    if segment_numbers is not None and waveform_ids is not None:
        raise ValueError("Use either segment_numbers or waveform_ids, not both")

    n_samples = int(channel_group.attrs["NumPoints"])
    n_waveforms = keysight_waveform_count(channel_group, waveform_dataset)
    row_indices = _select_waveform_rows(
        n_waveforms,
        segment_numbers=segment_numbers,
        waveform_ids=waveform_ids,
        segment_numbers_are_rows=table_segment_numbers_are_rows,
        np=np,
    )

    if len(row_indices) == 0:
        raw = np.empty((0, n_samples), dtype=dtype)
    elif np.array_equal(row_indices, np.arange(row_indices[0], row_indices[-1] + 1)):
        raw = read_keysight_waveform_rows(
            waveform_dataset,
            int(row_indices[0]),
            int(row_indices[-1]) + 1,
            n_samples,
            dtype=dtype,
        )
    else:
        raw = np.empty((len(row_indices), n_samples), dtype=dtype)
        for i, row_index in enumerate(row_indices):
            raw[i] = read_keysight_waveform_rows(
                waveform_dataset,
                int(row_index),
                int(row_index) + 1,
                n_samples,
                dtype=dtype,
            )[0]

    voltage = raw * float(channel_group.attrs["YInc"]) + float(channel_group.attrs["YOrg"])
    time = keysight_time_axis(channel_group, np=np, time_axis=time_axis)
    segment_numbers_out = row_indices.tolist() if table_segment_numbers_are_rows else (row_indices + 1).tolist()
    metadata = _keysight_metadata(
        h5_file,
        channel_group,
        channel_name=channel_name,
        segment_numbers=segment_numbers_out,
        layout="waveform_dataset",
    )
    metadata["x_origins"] = np.full(len(row_indices), float(channel_group.attrs.get("XOrg", 0.0)))
    metadata["time_tags"] = np.zeros(len(row_indices), dtype=float)
    metadata["waveform_dataset"] = waveform_dataset.name
    if include_raw:
        metadata["raw"] = raw

    return time, voltage, metadata


def _select_waveform_rows(
    n_waveforms: int,
    *,
    segment_numbers: Sequence[int] | None,
    waveform_ids: Sequence[int] | None,
    segment_numbers_are_rows: bool,
    np: Any,
) -> Any:
    if waveform_ids is not None:
        rows = np.array([int(waveform_id) for waveform_id in waveform_ids], dtype=int)
    elif segment_numbers is None:
        return np.arange(n_waveforms, dtype=int)
    elif segment_numbers_are_rows:
        rows = np.array([int(segment) for segment in segment_numbers], dtype=int)
    else:
        rows = np.array([int(segment) - 1 for segment in segment_numbers], dtype=int)

    bad = rows[(rows < 0) | (rows >= n_waveforms)]
    if len(bad):
        raise ValueError(f"waveform rows {bad.tolist()} are out of range")
    return rows


def _keysight_metadata(
    h5_file: Any,
    channel_group: Any,
    *,
    channel_name: str,
    segment_numbers: Sequence[int],
    layout: str,
) -> dict[str, Any]:
    return {
        "filename": str(Path(h5_file.filename)),
        "file_type": _read_dataset(h5_file, "FileType/KeysightH5FileType"),
        "frame": _read_dataset(h5_file, "Frame/TheFrame"),
        "channel": channel_name,
        "channel_attrs": attrs_to_dict(channel_group),
        "segment_numbers": list(segment_numbers),
        "layout": layout,
    }


def _no_waveforms_error(channel_group: Any) -> ValueError:
    available = ", ".join(channel_group.keys()) or "<empty>"
    return ValueError(
        f"No waveform datasets were found in {channel_group.name!r}. "
        "Expected segment datasets named like 'Channel 1 Seg1Data', a single "
        "unsegmented 1-D numeric dataset, or a waveform table like 'Channel 1Data'. "
        f"Available entries: {available}"
    )


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

    names_by_number = {
        segment_number(name, default=index + 1): name
        for index, name in enumerate(segment_names)
    }
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
