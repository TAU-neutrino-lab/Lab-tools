# Keysight HDF5 Oscilloscope Reader

Lab-tools includes a reader for segmented Keysight oscilloscope HDF5 files.
The main function is:

```python
from lab_tools.io import read_keysight_h5
```

## Example/Test Data

The repository includes a small HDF5 fixture at
`examples/data/run530_5waveforms.h5`. It is used by tests and examples, not as
real analysis data. It contains:

- five real Channel 1 segments copied from a random run 
- one synthetic Channel 2 with the same segment timing

Most users will open their own HDF5 files from an analysis repository, such as
`PMT-characterization`. 

## Basic Usage

```python
from lab_tools.io import read_keysight_h5

time, voltage, metadata = read_keysight_h5(
    "examples/data/run530_5waveforms.h5",
    segment_numbers=[1, 2, 3, 5],
)

print(metadata["frame"])
print(metadata["channel_attrs"]["XInc"])
print(time[:5])
print(voltage[0, :5])
```

The return values are:

- `time`: sample time axis
- `voltage`: array with shape `(n_waveforms, n_samples)`
- `metadata`: file, channel, and segment metadata from the HDF5 file

## Voltage Conversion

Keysight HDF5 waveforms are stored as raw integer samples. The reader applies
the same conversion used by Keysight CSV exports:

```python
voltage = raw * YInc + YOrg
```

`YInc` is the voltage step per raw ADC count. `YOrg` is the voltage offset. Both
come from the channel attributes in the HDF5 file, and the reader stores them in
`metadata["channel_attrs"]`:

```python
time, voltage, metadata = read_keysight_h5("run530.h5")

yinc = metadata["channel_attrs"]["YInc"]
yorg = metadata["channel_attrs"]["YOrg"]
units = metadata["channel_attrs"]["YUnits"]

print(yinc, yorg, units)
```

The conversion is already applied before `voltage` is returned. You only need
`YInc` and `YOrg` if you want to inspect the scaling or manually convert raw
samples loaded with `include_raw=True`.

## Time Axes

By default, the reader returns a relative time axis:

```python
time = sample_index * XInc
```

This is convenient for overlaying pulses from multiple segments.

Use `time_axis="absolute"` to include the segment timestamp and x-origin:

```python
time, voltage, metadata = read_keysight_h5(
    "run530.h5",
    segment_numbers=[1, 2, 3],
    time_axis="absolute",
)
```

In absolute mode:

```python
time = SegmentedTimeTag + SegmentedXOrg + sample_index * XInc
```

## Multiple Channels

Read channels separately because each channel has its own scaling and metadata:

```python
ch1_time, ch1_voltage, ch1_meta = read_keysight_h5(
    "examples/data/run530_5waveforms.h5",
    channel=1,
)

ch2_time, ch2_voltage, ch2_meta = read_keysight_h5(
    "examples/data/run530_5waveforms.h5",
    channel=2,
)
```

Segment numbers and time tags can be used to line up channel data from the same
acquisition:

```python
print(ch1_meta["segment_numbers"])
print(ch2_meta["segment_numbers"])
print(ch1_meta["time_tags"])
print(ch2_meta["time_tags"])
```

## Segment Time Tags Only

If you only need timing between segments, read the tags without loading the
waveform arrays:

```python
from lab_tools.io import read_segment_time_tags

segments, time_tags = read_segment_time_tags("examples/data/run530_5waveforms.h5")
```

## Notebook Example

```text
examples/keysight_h5_oscilloscope.ipynb
```
