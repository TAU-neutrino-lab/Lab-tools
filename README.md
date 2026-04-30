# Lab-tools

Shared tools for the TAU neutrino lab.

**Latest stable version: `v0.1.0`**

Use a tagged version for analysis work. Do not run analysis from `main`, because
`main` may change while tools are being developed.

## Users

These instructions are for people who want to use Lab-tools from another
repository, such as `PMT-characterization`.

### Repository Layout

Clone `Lab-tools` and analysis repositories side by side:

```text
TAU-neutrino-lab/
  Lab-tools/
  PMT-characterization/
```

### Check Out the Stable Tag

```bash
cd TAU-neutrino-lab/Lab-tools
git fetch --tags
git checkout v0.1.0
```

Seeing a detached-HEAD message after checking out a tag is normal. It means the
folder is pinned to that exact released version.

### Create the Python Environment

Create one Python environment for the analysis workspace:

```bash
cd TAU-neutrino-lab/Lab-tools

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install .
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

### Optional Jupyter Support

If you also want to use notebooks, install the notebook extras into the same
environment:

```bash
cd TAU-neutrino-lab/Lab-tools
source .venv/bin/activate

python -m pip install ".[notebooks]"
python -m ipykernel install --user --name tau-lab --display-name "TAU Lab"
```

In Jupyter or VS Code, choose the kernel named `TAU Lab`. Notebook imports are
then the same as regular Python imports:

```python
from lab_tools.io import read_keysight_h5
```

## Developers

These instructions are for modifying Lab-tools itself.

### Editable Install

Work from `main` when developing, and install in editable mode:

```bash
cd TAU-neutrino-lab/Lab-tools
git checkout main

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[notebooks]"
```

The `-e` flag installs Lab-tools in editable mode. Changes made inside
`Lab-tools/src/lab_tools` are picked up by this environment without reinstalling.

### Run Tests

```bash
cd TAU-neutrino-lab/Lab-tools
source .venv/bin/activate

python -m unittest discover -s tests
```

The tests use a small HDF5 fixture committed at
`examples/data/run530_5waveforms.h5`. It is only for examples and automated
checks; normal analysis should use the real data files from the analysis
repository.

### Tag a New Version

When the code is ready for users:

1. Update the version in `pyproject.toml`.
2. Update the highlighted latest stable version at the top of this README.
3. Run the tests.
4. Commit the changes.
5. Create and push an annotated tag.

Example:

```bash
python -m unittest discover -s tests

git add .
git commit -m "Release Lab-tools v0.1.1"

git tag -a v0.1.1 -m "Lab-tools v0.1.1"
git push
git push origin v0.1.1
```

Prefer making a new tag for a new stable version. Do not move an existing tag
unless you are deliberately fixing a bad release.

## Tool Documentation

- [Keysight HDF5 oscilloscope reader](docs/oscilloscope.md)
