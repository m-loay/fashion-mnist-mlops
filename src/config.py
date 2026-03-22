"""
config.py — Shared configuration loader for all pipeline stages.

Loads params.yaml once, provides typed access to base, paths,
and stage-specific parameters. All paths use pathlib.Path.

Usage:
    from config import load_config
    cfg = load_config()

    seed = cfg.base["seed"]
    raw_dir = cfg.paths["raw_dir"]       # returns Path object
    train_params = cfg.stage("train")
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class Config:
    """Typed configuration container."""

    base: dict = field(default_factory=dict)
    paths: dict = field(default_factory=dict)
    _raw: dict = field(default_factory=dict, repr=False)

    def stage(self, name: str) -> dict:
        """Get parameters for a specific pipeline stage."""
        if name not in self._raw:
            raise KeyError(
                f"Stage '{name}' not found in params.yaml. "
                f"Available: {[k for k in self._raw if k not in ('base', 'paths')]}"
            )
        return self._raw[name]

    def seed(self) -> int:
        return self.base["seed"]

    def dropout(self) -> float:
        return self.base["dropout"]

    def num_classes(self) -> int:
        return self.base["num_classes"]

    def class_names(self) -> list[str]:
        return self.base["class_names"]


def load_config(params_path: str = "params.yaml") -> Config:
    """
    Load params.yaml and return a Config object.

    All values under 'paths' are converted to pathlib.Path objects.
    """
    params_file = Path(params_path)
    if not params_file.exists():
        raise FileNotFoundError(f"Config file not found: {params_file}")

    with open(params_file) as f:
        raw = yaml.safe_load(f)

    # Convert path strings to Path objects
    paths = {key: Path(value) for key, value in raw.get("paths", {}).items()}

    return Config(
        base=raw.get("base", {}),
        paths=paths,
        _raw=raw,
    )
