"""
preprocess.py — Normalize, reshape, and split raw data.

Reads raw .npy files from paths.raw_dir.
Outputs processed .npy files to paths.processed_dir.

Operations:
  1. Normalize pixel values to [0, 1]
  2. Reshape: add channel dim for CNN or flatten for dense
  3. Split train into train + validation sets
"""

import numpy as np
from pathlib import Path
from config import load_config


def normalize(X: np.ndarray) -> np.ndarray:
    """Normalize to [0, 1] float32."""
    return X.astype("float32") / 255.0


def reshape_for_cnn(X: np.ndarray) -> np.ndarray:
    """Add channel dimension: (N, 28, 28) → (N, 28, 28, 1)."""
    return X[..., np.newaxis]


def flatten_images(X: np.ndarray) -> np.ndarray:
    """Flatten spatial dims: (N, 28, 28) → (N, 784)."""
    return X.reshape(X.shape[0], -1)


def split_train_val(
    X: np.ndarray,
    y: np.ndarray,
    val_ratio: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split training data into train and validation sets."""
    rng = np.random.RandomState(seed)
    n_total = len(X)
    n_val = int(n_total * val_ratio)
    indices = rng.permutation(n_total)
    val_idx, train_idx = indices[:n_val], indices[n_val:]

    return X[train_idx], y[train_idx], X[val_idx], y[val_idx]


def main():
    # load config and params
    cfg = load_config()
    params = cfg.stage("preprocess")
    raw_dir: Path = cfg.paths["raw_dir"]
    processed_dir: Path = cfg.paths["processed_dir"]
    seed = cfg.seed()

    print("=" * 50)
    print("STAGE: preprocess")
    print("=" * 50)

    # Load raw data
    X_train_full = np.load(raw_dir / "X_train.npy")
    y_train_full = np.load(raw_dir / "y_train.npy")
    X_test = np.load(raw_dir / "X_test.npy")
    y_test = np.load(raw_dir / "y_test.npy")
    print(f"Loaded raw: train={X_train_full.shape}, test={X_test.shape}")

    # 1. Normalize
    if params["normalize"]:
        X_train_full = normalize(X_train_full)
        X_test = normalize(X_test)
        print("Normalized to [0, 1]")

    # 2. Reshape
    if params["flatten"]:
        X_train_full = flatten_images(X_train_full)
        X_test = flatten_images(X_test)
        print(f"Flattened: {X_train_full.shape}")
    else:
        X_train_full = reshape_for_cnn(X_train_full)
        X_test = reshape_for_cnn(X_test)
        print(f"Reshaped for CNN: {X_train_full.shape}")

    # 3. Split
    X_train, y_train, X_val, y_val = split_train_val(
        X_train_full,
        y_train_full,
        val_ratio=params["validation_split"],
        seed=seed,
    )

    print(f"Split: train={X_train.shape}, val={X_val.shape}, test={X_test.shape}")

    # 4. Save
    processed_dir.mkdir(parents=True, exist_ok=True)
    np.save(processed_dir / "X_train.npy", X_train)
    np.save(processed_dir / "y_train.npy", y_train)
    np.save(processed_dir / "X_val.npy", X_val)
    np.save(processed_dir / "y_val.npy", y_val)
    np.save(processed_dir / "X_test.npy", X_test)
    np.save(processed_dir / "y_test.npy", y_test)

    print(f"Saved to {processed_dir}/")
    print("DONE\n")


if __name__ == "__main__":
    main()
