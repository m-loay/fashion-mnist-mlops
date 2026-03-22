"""
builder.py — Build Keras model from architecture YAML config.

No magic numbers: dropout, num_classes, and input_shape are all
passed explicitly from params.yaml via the calling code.

Usage:
    from builder import build_model

    model = build_model(
        arch_config_path=Path("configs/cnn_basic.yml"),
        input_shape=(28, 28, 1),
        num_classes=10,
        dropout=0.3,       # from base.dropout
    )
"""

from pathlib import Path

import yaml
from tensorflow import keras
from tensorflow.keras import layers


# ─────────────────────────────────────────────────
# Layer builders — one function per layer type
# ─────────────────────────────────────────────────


def _conv2d(x, def_: dict, name: str):
    return layers.Conv2D(
        filters=def_["filters"],
        kernel_size=tuple(def_["kernel_size"]),
        activation=def_.get("activation", "relu"),
        padding=def_.get("padding", "same"),
        name=name,
    )(x)


def _batch_norm(x, def_: dict, name: str):
    return layers.BatchNormalization(name=name)(x)


def _max_pool2d(x, def_: dict, name: str):
    return layers.MaxPooling2D(
        pool_size=tuple(def_["pool_size"]),
        name=name,
    )(x)


def _global_avg_pool2d(x, def_: dict, name: str):
    return layers.GlobalAveragePooling2D(name=name)(x)


def _flatten(x, def_: dict, name: str):
    return layers.Flatten(name=name)(x)


def _dense(x, def_: dict, name: str):
    return layers.Dense(
        units=def_["units"],
        activation=def_.get("activation", "relu"),
        name=name,
    )(x)


def _dropout(x, def_: dict, name: str):
    return layers.Dropout(rate=def_["rate"], name=name)(x)


def _reshape(x, def_: dict, name: str):
    import numpy as np

    if def_.get("target_shape") == "auto":
        shape = x.shape
        if len(shape) == 4:
            time_steps = shape[1]
            features = int(np.prod(shape[2:]))
            return layers.Reshape((time_steps, features), name=name)(x)
        return layers.Flatten(name=name)(x)
    return layers.Reshape(tuple(def_["target_shape"]), name=name)(x)


def _lstm(x, def_: dict, name: str):
    return layers.LSTM(
        units=def_["units"],
        return_sequences=def_.get("return_sequences", False),
        name=name,
    )(x)


def _gru(x, def_: dict, name: str):
    return layers.GRU(
        units=def_["units"],
        return_sequences=def_.get("return_sequences", False),
        name=name,
    )(x)


# Registry: layer type string → builder function
_LAYER_BUILDERS = {
    "conv2d": _conv2d,
    "batch_norm": _batch_norm,
    "max_pool2d": _max_pool2d,
    "global_avg_pool2d": _global_avg_pool2d,
    "flatten": _flatten,
    "dense": _dense,
    "dropout": _dropout,
    "reshape": _reshape,
    "lstm": _lstm,
    "gru": _gru,
}


# ─────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────


def build_model(
    arch_config_path: Path,
    input_shape: tuple,
    num_classes: int,
    dropout: float,
) -> keras.Model:
    """
    Build a Keras model from an architecture YAML file.

    Args:
        arch_config_path: Path to architecture YAML (e.g. configs/cnn_basic.yml)
        input_shape: Input tensor shape, from data (e.g. (28, 28, 1))
        num_classes: Number of output classes, from base.num_classes
        dropout: Final dropout rate, from base.dropout

    Returns:
        Uncompiled Keras Model
    """
    arch_config_path = Path(arch_config_path)

    with open(arch_config_path) as f:
        arch = yaml.safe_load(f)

    description = arch.get("description", "No description")
    layer_defs = arch["layers"]
    model_name = arch_config_path.stem

    print(f"Building model: {model_name}")
    print(f"  Description:  {description}")
    print(f"  Input shape:  {input_shape}")
    print(f"  Num classes:  {num_classes}")
    print(f"  Dropout:      {dropout}")
    print(f"  Layers:       {len(layer_defs)}")

    # Build functional model
    inputs = keras.Input(shape=input_shape, name="input")
    x = inputs

    for i, layer_def in enumerate(layer_defs):
        layer_type = layer_def["type"]
        name = f"{layer_type}_{i}"

        builder_fn = _LAYER_BUILDERS.get(layer_type)
        if builder_fn is None:
            supported = ", ".join(sorted(_LAYER_BUILDERS.keys()))
            raise ValueError(
                f"Unknown layer type '{layer_type}' at index {i}. " f"Supported: {supported}"
            )

        x = builder_fn(x, layer_def, name)

    # Classification head (no magic numbers — all from params)
    x = layers.Dropout(dropout, name="final_dropout")(x)
    outputs = layers.Dense(num_classes, activation="softmax", name="output")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name=model_name)
    print(f"  Parameters:   {model.count_params():,}")

    return model
