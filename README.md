# Lab-tools

Shared Python tools for the `TAU-neutrino-lab` GitHub organization.

The repository starts small: shared oscilloscope IO for PMT calibration data.
The package layout is meant to grow naturally as more shared IO, data handling,
PMT characterization, and simulation utilities are added.

The example HDF5 file at `examples/data/run530_5waveforms.h5` contains five
real Channel 1 segments from `run530.h5` plus a synthetic Channel 2 with the
same segment timing for multi-channel examples.

## Install from a local checkout

```bash
python -m pip install -e .
```

## Run tests

```bash
python -m unittest discover -s tests
```

## Use the oscilloscope reader

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

Keysight HDF5 waveforms are stored as raw integer samples. The reader applies
the same conversion used by the PMT CSV exports:

```python
voltage = raw * YInc + YOrg
```

By default, the reader returns the notebook-style relative time axis:

```python
time = sample_index * XInc
```

Use `time_axis="absolute"` to include the segment timestamp and x-origin:

```python
time, voltage, metadata = read_keysight_h5("run530.h5", time_axis="absolute")
```

## Suggested repository structure

```text
Lab-tools/
  src/lab_tools/
    io/
      oscilloscope.py
  tests/
    data/
  examples/
```

Future additions can go under focused modules such as:

```text
src/lab_tools/pmt/
src/lab_tools/simulation/
src/lab_tools/data/
```

## Install from another repository

Once this repository is pushed to GitHub and tagged, other repositories can pin
a version:

```toml
dependencies = [
  "lab-tools @ git+ssh://git@github.com/TAU-neutrino-lab/Lab-tools.git@v0.1.0",
]
```

Pinning a tag keeps old analyses reproducible while allowing this package to
evolve.
