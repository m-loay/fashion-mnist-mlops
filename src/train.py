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
    print("Loading config...")
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

    # Train with DVCLive — manual epoch loop for combined plots
    models_dir.mkdir(parents=True, exist_ok=True)
    epochs = train_params["epochs"]
    batch_size = train_params["batch_size"]

    with Live(dir=str(dvclive_dir), report="html") as live:
        # Log params for DVC Studio columns
        live.log_param("arch_config", str(arch_config))
        live.log_param("arch_name", arch_config.stem)
        live.log_param("epochs", epochs)
        live.log_param("batch_size", batch_size)
        live.log_param("lr", train_params["lr"])
        live.log_param("optimizer", train_params["optimizer"])
        live.log_param("dropout", dropout)
        live.log_param("total_params", model.count_params())
        live.log_param("seed", seed)

        # Train epoch by epoch — log train + val on same step
        history = None
        for epoch in range(epochs):
            print(f"\nEpoch {epoch + 1}/{epochs}")
            history = model.fit(
                X_train,
                y_train,
                validation_data=(X_val, y_val),
                epochs=1,
                batch_size=batch_size,
                verbose=1,
            )

            # Same prefix → same graph in DVC plots
            live.log_metric("loss/train", history.history["loss"][0])
            live.log_metric("loss/val", history.history["val_loss"][0])
            live.log_metric("accuracy/train", history.history["accuracy"][0])
            live.log_metric("accuracy/val", history.history["val_accuracy"][0])
            live.next_step()

        # Final summary metrics
        if history is not None:
            final_train_acc = history.history["accuracy"][-1]
            final_val_acc = history.history["val_accuracy"][-1]
            final_train_loss = history.history["loss"][-1]
            final_val_loss = history.history["val_loss"][-1]
        else:
            final_train_acc = final_val_acc = final_train_loss = final_val_loss = 0.0

        live.summary["final_train_accuracy"] = round(final_train_acc, 4)
        live.summary["final_val_accuracy"] = round(final_val_acc, 4)
        live.summary["final_train_loss"] = round(final_train_loss, 4)
        live.summary["final_val_loss"] = round(final_val_loss, 4)

    # Save model
    model_path = models_dir / "model.keras"
    model.save(model_path)
    print(f"\nModel saved to {model_path}")
    print(f"Training complete: val_accuracy={final_val_acc:.4f}")
    print("DONE\n")


if __name__ == "__main__":
    main()
