"""
train.py — Train model with DVCLive experiment tracking.

All config from params.yaml via config.py:
  - base.seed, base.dropout, base.num_classes
  - paths.processed_dir, paths.models_dir, paths.dvclive_dir
  - train.* (arch_config, epochs, batch_size, lr, optimizer)
"""

import os
import json
import numpy as np
import tensorflow as tf
from pathlib import Path
from dvclive.live import Live
from dvclive.keras import DVCLiveCallback


from config import load_config
from builder import build_model


def get_optimizer(name: str, lr: float) -> tf.keras.optimizers.Optimizer:
    """Create optimizer by name from params."""
    optimizers = {
        "adam": tf.keras.optimizers.Adam,
        "sgd": tf.keras.optimizers.SGD,
        "rmsprop": tf.keras.optimizers.RMSprop,
    }
    opt_class = optimizers.get(name)
    if opt_class is None:
        raise ValueError(f"Unknown optimizer: '{name}'. Use: {list(optimizers.keys())}")
    return opt_class(learning_rate=lr)


def main():
    cfg = load_config()
    train_params = cfg.stage("train")

    # Paths from config
    processed_dir: Path = cfg.paths["processed_dir"]
    models_dir: Path = cfg.paths["models_dir"]
    dvclive_dir: Path = cfg.paths["dvclive_dir"]
    arch_config = Path(train_params["arch_config"])

    # Base config
    seed = cfg.seed()
    dropout = cfg.dropout()
    num_classes = cfg.num_classes()

    print("=" * 50)
    print("STAGE: train")
    print(f"Architecture: {arch_config}")
    print("=" * 50)

    # Reproducibility
    tf.random.set_seed(seed)
    np.random.seed(seed)

    # Load processed data
    X_train = np.load(processed_dir / "X_train.npy")
    y_train = np.load(processed_dir / "y_train.npy")
    X_val = np.load(processed_dir / "X_val.npy")
    y_val = np.load(processed_dir / "y_val.npy")

    input_shape = X_train.shape[1:]
    print(f"Train: {X_train.shape}, Val: {X_val.shape}")
    print(f"Input shape: {input_shape}, Classes: {num_classes}")

    # Build model — all params explicit, no magic numbers
    model = build_model(
        arch_config_path=arch_config,
        input_shape=input_shape,
        num_classes=num_classes,
        dropout=dropout,
    )

    # Compile
    optimizer = get_optimizer(train_params["optimizer"], train_params["lr"])
    model.compile(
        optimizer=optimizer,
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.summary()

    # Train with DVCLive
    models_dir.mkdir(parents=True, exist_ok=True)

    with Live(dir=str(dvclive_dir), report="html") as live:
        # Log params for DVC Studio columns
        live.log_param("arch_config", str(arch_config))
        live.log_param("arch_name", arch_config.stem)
        live.log_param("epochs", train_params["epochs"])
        live.log_param("batch_size", train_params["batch_size"])
        live.log_param("lr", train_params["lr"])
        live.log_param("optimizer", train_params["optimizer"])
        live.log_param("dropout", dropout)
        live.log_param("total_params", model.count_params())
        live.log_param("seed", seed)

        # Train
        history = model.fit(
            X_train,
            y_train,
            validation_data=(X_val, y_val),
            epochs=train_params["epochs"],
            batch_size=train_params["batch_size"],
            callbacks=[DVCLiveCallback(live=live)],
            verbose=1,
        )

        # Log final metrics
        final = {
            "final_train_accuracy": round(history.history["accuracy"][-1], 4),
            "final_val_accuracy": round(history.history["val_accuracy"][-1], 4),
            "final_train_loss": round(history.history["loss"][-1], 4),
            "final_val_loss": round(history.history["val_loss"][-1], 4),
        }
        for key, value in final.items():
            live.summary[key] = value

    # Save model
    model_path = models_dir / "model.keras"
    model.save(model_path)
    print(f"\nModel saved to {model_path}")
    print(f"Training complete: val_accuracy={final['final_val_accuracy']}")
    print("DONE\n")


if __name__ == "__main__":
    main()
