from pathlib import Path
from typing import Any, Dict, Union
import tomlkit


def read_toml(path: Union[Path, str]) -> Dict[str, Any]:
    with Path(path).open("r") as f:
        return tomlkit.load(f)


def write_toml(data: Dict[str, Any], path: Union[Path, str]) -> None:
    with Path(path).open("w") as f:
        return tomlkit.dump(data, f)
