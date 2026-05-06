# Lab-tools

Shared tools for the TAU neutrino lab.

**Latest stable version: `v0.1.3`**

Use a tagged version for analysis work. Do not run analysis from `main`, because
`main` may change while tools are being developed.

### Check Out the Stable Tag

```bash
cd TAU-neutrino-lab/Lab-tools
git fetch --tags
git checkout v0.1.3
```

Seeing a detached-HEAD message after checking out a tag is normal. It means the
folder is pinned to that exact released version.

## Installation (to do once)

These instructions are for people who want to use Lab-tools from another
repository, such as `PMT-characterization`.

### Repository Layout

Clone `Lab-tools` and analysis repositories side by side:

```text
TAU-neutrino-lab/
  Lab-tools/
  PMT-characterization/
```

### Linux / macOS users

#### Create Python Environment 

Create a virtual python environment in the Lab-tools repository

```bash
cd TAU-neutrino-lab/Lab-tools

python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install .
```

#### Install Jupyter kernels

If you also want to use notebooks, install the notebook extras into the same environment:

```bash
# cd TAU-neutrino-lab/Lab-tools
# source .venv/bin/activate
python -m pip install ".[notebooks]"
python -m ipykernel install --user --name tau-lab --display-name "TAU Lab"
```

In Jupyter or VS Code, choose the kernel named `TAU Lab`. 

### Windows (PowerShell) users

#### Create Python Environment 

Create a virtual python environment in the Lab-tools repository

```powershell
cd TAU-neutrino-lab/Lab-tools

python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install .
```

If PowerShell blocks activation scripts, run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then retry:

```powershell
.\.venv\Scripts\activate
```

#### Install Jupyter kernels

If you also want to use notebooks, install the notebook extras into the same environment:

```bash
# cd TAU-neutrino-lab/Lab-tools
# .\.venv\Scripts\activate
python -m pip install ".[notebooks]"
python -m ipykernel install --user --name tau-lab --display-name "TAU Lab"
```

### Usage

Once the environment is created, it can be used in any of the other repositories of TAU-neutrino-lab after activation

```bash
cd TAU-neutrino-lab/Lab-tools
source .venv/bin/activate # Linux / Mac
.\.venv\Scripts\activate # Windows
```

See examples for practical information on how to call the different functions within a script or in a notebook


## Developers

Work from `main` when developing, and install in editable mode:

<!-- ```bash
cd TAU-neutrino-lab/Lab-tools
git checkout main

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[notebooks]"
```

The `-e` flag installs Lab-tools in editable mode. Changes made inside
`Lab-tools/src/lab_tools` are picked up by this environment without reinstalling. -->

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
# always run the tests before tagging
python -m unittest discover -s tests

git add .
git commit -m "Release Lab-tools v0.1.3"

git tag -a v0.1.3 -m "Lab-tools v0.1.3"
git push
git push origin v0.1.3
```

Prefer making a new tag for a new stable version. Do not move an existing tag
unless you are deliberately fixing a bad release.

## Tool Documentation

- [Keysight HDF5 oscilloscope reader](docs/oscilloscope.md)
