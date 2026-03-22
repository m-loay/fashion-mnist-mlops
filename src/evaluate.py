"""
evaluate.py — Evaluate trained model on test set.

All config from params.yaml via config.py:
  - base.num_classes, base.class_names
  - paths.processed_dir, paths.models_dir, paths.metrics_dir
  - evaluate.* (save flags)

Produces:
  - metrics/eval.json              (DVC-tracked metrics)
  - metrics/confusion_matrix.csv   (DVC Studio plot)
  - metrics/confusion_matrix.png   (visual artifact)
  - metrics/classification_report.json
"""

import json
import numpy as np
import tensorflow as tf
from pathlib import Path
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    confusion_matrix,
    classification_report,
)

from config import load_config


def save_confusion_matrix_csv(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_names: list[str],
    path: Path,
) -> None:
    """Save confusion matrix as CSV for DVC Studio plotting."""
    cm = confusion_matrix(y_true, y_pred)
    rows = []
    for i, actual in enumerate(class_names):
        for j, predicted in enumerate(class_names):
            rows.append(f"{actual},{predicted},{cm[i][j]}")

    path.write_text("actual,predicted,count\n" + "\n".join(rows))
    print(f"Saved {path}")


def save_confusion_matrix_plot(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_names: list[str],
    path: Path,
) -> None:
    """Save confusion matrix as PNG image."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cm = confusion_matrix(y_true, y_pred)
    cm_norm = cm.astype("float") / cm.sum(axis=1)[:, np.newaxis]

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(cm_norm, interpolation="nearest", cmap=plt.cm.Blues)
    ax.figure.colorbar(im, ax=ax)

    n = len(class_names)
    ax.set(
        xticks=np.arange(n), yticks=np.arange(n),
        xticklabels=class_names, yticklabels=class_names,
        ylabel="True label", xlabel="Predicted label",
        title="Confusion Matrix (normalized)",
    )
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    thresh = cm_norm.max() / 2.0
    for i in range(n):
        for j in range(n):
            ax.text(
                j, i, f"{cm_norm[i, j]:.2f}",
                ha="center", va="center",
                color="white" if cm_norm[i, j] > thresh else "black",
                fontsize=7,
            )

    fig.tight_layout()
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved {path}")


def main():
    cfg = load_config()
    eval_params = cfg.stage("evaluate")

    # Paths from config
    processed_dir: Path = cfg.paths["processed_dir"]
    models_dir: Path = cfg.paths["models_dir"]
    metrics_dir: Path = cfg.paths["metrics_dir"]

    # Base config
    class_names = cfg.class_names()
    num_classes = cfg.num_classes()

    print("=" * 50)
    print("STAGE: evaluate")
    print("=" * 50)

    # Load model and test data
    model_path = models_dir / "model.keras"
    model = tf.keras.models.load_model(model_path)
    X_test = np.load(processed_dir / "X_test.npy")
    y_test = np.load(processed_dir / "y_test.npy")
    print(f"Model: {model_path}")
    print(f"Test set: {X_test.shape}")

    # Predict
    y_proba = model.predict(X_test, verbose=0)
    y_pred = np.argmax(y_proba, axis=1)

    # Compute metrics
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="weighted")
    precision = precision_score(y_test, y_pred, average="weighted")
    recall = recall_score(y_test, y_pred, average="weighted")

    print(f"\nTest Results:")
    print(f"  Accuracy:  {acc:.4f}")
    print(f"  F1:        {f1:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")

    # Save metrics (DVC tracks this)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    eval_metrics = {
        "test_accuracy": round(acc, 4),
        "test_f1": round(f1, 4),
        "test_precision": round(precision, 4),
        "test_recall": round(recall, 4),
        "test_samples": len(y_test),
    }
    eval_json_path = metrics_dir / "eval.json"
    eval_json_path.write_text(json.dumps(eval_metrics, indent=2))
    print(f"Saved {eval_json_path}")

    # Confusion matrix CSV (DVC Studio plots this)
    cm_csv_path = metrics_dir / "confusion_matrix.csv"
    save_confusion_matrix_csv(y_test, y_pred, class_names, cm_csv_path)

    # Confusion matrix image
    if eval_params.get("save_confusion_matrix", True):
        cm_png_path = metrics_dir / "confusion_matrix.png"
        save_confusion_matrix_plot(y_test, y_pred, class_names, cm_png_path)

    # Classification report
    if eval_params.get("save_classification_report", True):
        report = classification_report(
            y_test, y_pred,
            target_names=class_names,
            output_dict=True,
        )
        report_path = metrics_dir / "classification_report.json"
        report_path.write_text(json.dumps(report, indent=2))
        print(f"Saved {report_path}")

        print(f"\nPer-class F1:")
        for name in class_names:
            if name in report:
                print(f"  {name:15s}: {report[name]['f1-score']:.3f}")

    print("\nDONE\n")


if __name__ == "__main__":
    main()
