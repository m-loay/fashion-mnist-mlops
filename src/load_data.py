"""
load_data.py — Load raw data from one of three sources.

Sources:
  - "download": Fetch Fashion MNIST via tf.keras.datasets (default)
  - "local":    Load from an existing local directory
  - "s3":       Download from an S3 URI using AWS CLI

Saves raw numpy arrays to paths.raw_dir for DVC tracking.
"""

import subprocess
import numpy as np
import tensorflow as tf
import keras

from pathlib import Path
from config import load_config


def load_from_download(raw_dir: Path) -> None:
    """Download Fashion MNIST from TensorFlow datasets."""
    print("Source: download (tf.keras.datasets)")
    (X_train, y_train), (X_test, y_test) = keras.datasets.fashion_mnist.load_data()
    _save_raw(raw_dir, X_train, y_train, X_test, y_test)


def load_from_local(raw_dir: Path, local_path: str) -> None:
    """Load raw data from an existing local directory."""
    src = Path(local_path)
    print(f"Source: local ({src})")

    if not src.exists():
        raise FileNotFoundError(f"Local data path not found: {src}")

    X_train = np.load(src / "X_train.npy")
    y_train = np.load(src / "y_train.npy")
    X_test = np.load(src / "X_test.npy")
    y_test = np.load(src / "y_test.npy")
    _save_raw(raw_dir, X_train, y_train, X_test, y_test)


def load_from_s3(raw_dir: Path, s3_uri: str) -> None:
    """Download raw data from S3 using AWS CLI."""
    print(f"Source: s3 ({s3_uri})")

    raw_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["aws", "s3", "cp", s3_uri, str(raw_dir), "--recursive"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"S3 download failed: {result.stderr}")

    print(f"Downloaded from {s3_uri}")

    # Verify expected files exist
    for name in ["X_train.npy", "y_train.npy", "X_test.npy", "y_test.npy"]:
        if not (raw_dir / name).exists():
            raise FileNotFoundError(
                f"Expected file {name} not found in {raw_dir} after S3 download"
            )


def _save_raw(
    raw_dir: Path,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> None:
    """Save raw arrays to disk."""
    raw_dir.mkdir(parents=True, exist_ok=True)

    np.save(raw_dir / "X_train.npy", X_train)
    np.save(raw_dir / "y_train.npy", y_train)
    np.save(raw_dir / "X_test.npy", X_test)
    np.save(raw_dir / "y_test.npy", y_test)

    print(f"Saved: X_train={X_train.shape}, X_test={X_test.shape}")
    print(f"Labels: {np.unique(y_train)}")


def main():
    # load config and params
    cfg = load_config()
    params = cfg.stage("load_data")
    raw_dir = cfg.paths["raw_dir"]
    source = params["source"]

    print("=" * 50)
    print("STAGE: load_data")
    print("=" * 50)

    if source == "download":
        print("Source: download (tf.keras.datasets)")
        load_from_download(raw_dir)
    elif source == "local":
        print("Source: local")
        local_path = params.get("local_path")
        if not local_path:
            raise ValueError("load_data.local_path must be set when source=local")
        load_from_local(raw_dir, local_path)
    elif source == "s3":
        print("Source: s3")
        s3_uri = params.get("s3_uri")
        if not s3_uri:
            raise ValueError("load_data.s3_uri must be set when source=s3")
        load_from_s3(raw_dir, s3_uri)
    else:
        raise ValueError(f"Unknown source: '{source}'. Use 'download', 'local', or 's3'.")

    print("DONE\n")


if __name__ == "__main__":
    main()
