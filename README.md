# Lab-tools

Shared tools for the TAU neutrino lab.

This repository is meant to be installed once into the Python environment used
by analysis repositories such as `PMT-characterization`.

## Repository Layout

Clone `Lab-tools` and analysis repositories side by side:

```text
TAU-neutrino-lab/
  Lab-tools/
  PMT-characterization/
```

## Python Environment

Create one Python environment for the analysis workspace:

```bash
cd TAU-neutrino-lab/Lab-tools

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e .
```

After this, Python scripts in any sibling repository can import Lab-tools as
long as the environment is activated:

```bash
cd ../PMT-characterization/PMT-calibration
python my_script.py
```

```python
from lab_tools.io import read_keysight_h5
```

The `-e` flag installs Lab-tools in editable mode. Changes made inside
`Lab-tools/src/lab_tools` are picked up by this environment without reinstalling.

## Optional Jupyter Support (recommended)

If you also want to use notebooks, install the notebook extras into the same
environment:

```bash
cd TAU-neutrino-lab/Lab-tools
source .venv/bin/activate

python -m pip install -e ".[notebooks]"
python -m ipykernel install --user --name tau-lab --display-name "TAU Lab"
```

In Jupyter, choose the kernel named `TAU Lab`. Notebook imports are then the
same as regular Python imports:

```python
from lab_tools.io import read_keysight_h5
```

## Run Tests

Runs automatic checks on the files.

Unless you want to modify the python scripts in this repo you won't need this.

```bash
cd TAU-neutrino-lab/Lab-tools
source .venv/bin/activate

python -m unittest discover -s tests
```

## Tool Documentation

- [Keysight HDF5 oscilloscope reader](docs/oscilloscope.md)
