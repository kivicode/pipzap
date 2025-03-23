# ⚡️ PipZap ⚡

[![image](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![Python Versions](https://img.shields.io/badge/python-3.8%20|%203.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13-blue)

> Zap the mess out of the dependency jungles

## Overview

PipZap is a command-line tool created to optimize Python dependency management by pruning redundant dependencies and merging multiple dependency files into a streamlined list.

Leveraging [uv](https://github.com/astral-sh/uv) for dependency resolution, it supports `requirements.txt`, uv’s `pyproject.toml`, and Poetry’s `pyproject.toml` (both legacy and modern formats). PipZap ensures your dependency declarations are as lean as possible without compromising functionality.

## Why PipZap?

Python dependency management can be a mess, especially with scientific libraries where outdated practices persist. Projects (even recent ones) often ship with a `requirements.txt` generated by `pip freeze`, leaving you with a sprawling list of pinned dependencies, many of which are redundant.

Take the [easy_ViTPose](https://github.com/JunkyByte/easy_ViTPose) project as an example: its [requirements.txt](https://github.com/JunkyByte/easy_ViTPose/blob/main/requirements.txt) lists over 40 packages, including transitive dependencies like `certifi` and `numpy`.

> See [below](#pruning-requirementstxt-from-easy_vitpose) for a real example with VitPose

PipZap can transform this into a concise, modern format such as [poetry](https://github.com/python-poetry/poetry), [uv](https://github.com/astral-sh/uv), or even a good old `requirements.txt` with just the essential direct dependencies. This makes it much easier to
adopt any package into a modern codebase.

Moreover, even in well-maintained codebases, accidental over-specification creeps in, and PipZap cuts through that noise, keeping your dependency list clean and intentional.

## Features

- **Dependency Pruning**: Removes redundant dependencies satisfied by transitive dependencies.
- **Multi-File Merging**: Combines and prunes dependencies from multiple sources.
- **Format Auto-Detection**: Automatically identifies `requirements.txt`, uv, and Poetry files.
- **Flexible Output**: Supports outputting in `requirements`, `poetry`, or `uv` formats.
- **Python Version Handling**: Extracts from `pyproject.toml` or accepts via CLI for `requirements.txt`.
- **Verbose Logging**: Optional rich logging for detailed insights.

## Installation

Install PipZap via pip:

```bash
pip install pipzap
```

## Usage

PipZap offers two main commands: `prune` and `merge-prune`, with options for verbosity, Python version, output file, and format.

### Prune a Single File

Eliminate redundant dependencies from a single file:

```bash
pipzap requirements.txt -p 3.11
pipzap pyproject.toml
pipzap pyproject.toml -o pruned.txt -v
```

- Use `-p/--python-version` for `requirements.txt` (required).
- Python version is auto-detected from `pyproject.toml` if present.

### Merge and Prune Multiple Files

Merge and prune dependencies from multiple files:

```bash
pipzap merge-prune requirements.txt pyproject.toml -o merged.txt -p 3.11 -f poetry
```

- `-p/--python-version` is required if any file is `requirements.txt`.

## Supported Formats

- **`requirements.txt`**: Pip-style with `--extra-index-url` support.
- **UV `pyproject.toml`**: Parses `[project.dependencies]` and `[project.requires-python]`.
- **Poetry `pyproject.toml`**: Handles `[project.dependencies]` (modern) and `[tool.poetry.dependencies]` (legacy).

## How It Works

1. **Parsing**: Detects file format and extracts direct dependencies.
2. **Resolution**: Uses `uv` to resolve the full dependency graph via a temporary `pyproject.toml`.
3. **Pruning**: Identifies and removes transitive redundancies.
4. **Merging**: Combines multiple files into a single pruned list.
5. **Formatting**: Outputs in the specified format (`requirements`, `poetry`, or `uv`).

## Examples

### Pruning `requirements.txt` from `easy_ViTPose`

Input (`requirements.txt` from [easy_ViTPose](https://github.com/JunkyByte/easy_ViTPose/blob/main/requirements.txt)):

```
certifi==2023.7.22
charset-normalizer==3.2.0
coloredlogs==15.0.1
contourpy==1.1.1
cycler==0.11.0
ffmpeg==1.4
filelock==3.12.4
filterpy==1.4.5
flatbuffers==23.5.26
fonttools==4.43.0
humanfriendly==10.0
idna==3.4
imageio==2.31.3
importlib-resources==6.1.0
jinja2>=3.1.3
kiwisolver==1.4.5
lazy_loader==0.3
MarkupSafe==2.1.3
matplotlib==3.8.0
mpmath==1.3.0
networkx==3.1
numpy==1.26.0
onnx==1.14.1
onnxruntime==1.16.0
opencv-python==4.8.0.76
packaging==23.1
pandas==2.1.1
Pillow>=10.2.0
protobuf==4.24.3
psutil==5.9.5
py-cpuinfo==9.0.0
pycocotools==2.0.8
pyparsing==3.1.1
python-dateutil==2.8.2
pytz==2023.3.post1
PyWavelets==1.4.1
PyYAML==6.0.1
requests==2.31.0
scikit-image==0.21.0
scipy==1.11.2
seaborn==0.12.2
six==1.16.0
sympy==1.12
tifffile==2023.9.18
tqdm==4.66.1
typing_extensions==4.8.0
tzdata==2023.3
ultralytics==8.2.48
urllib3>=2.0.7
zipp==3.17.0
```

Command:

```bash
pipzap prune requirements.txt -p 3.11 -f poetry
```

Output (pruned to direct dependencies):

```toml
[tool.poetry.dependencies]
ffmpeg = "1.4"
filterpy = "1.4.5"
importlib-resources = "6.1.0"
lazy_loader = "0.3"
onnx = "1.14.1"
onnxruntime = "1.16.0"
pycocotools = "2.0.8"
scikit-image = "0.21.0"
typing_extensions = "4.8.0"
ultralytics = "8.2.48"
zipp = "3.17.0"
```

### Merging and Pruning with Poetry Output

Input (`reqs.txt`):

```
requests==2.28.1
```

Input (`pyproject.toml`):

```toml
[project]
dependencies = [
 "urllib3>=1.26.9",
 "flask==2.0.1",
]
requires-python = ">=3.9"
```

Command:

```bash
pipzap merge-prune reqs.txt pyproject.toml -p 3.11 -f poetry
```

Output (assuming `urllib3` is transitive):

```toml
[tool.poetry.dependencies]
requests = "2.28.1"
flask = "2.0.1"
```

## Contributing

Contributions are encouraged! To contribute:

1. Fork the repository.
2. Install dev dependencies: `pip install -e .[dev]`.
3. Run tests: `pytest`.
4. Submit a pull request.

Follow the [Ruff](https://github.com/charliermarsh/ruff) linting rules and ensure type safety with [mypy](https://mypy.readthedocs.io/).

## License

PipZap is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- Powered by [uv](https://github.com/astral-sh/uv) for dependency resolution.
- Born from the chaos of overgrown Python dependency lists.
