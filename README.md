# Fashion MNIST MLOps Pipeline

A production-grade MLOps pipeline using **DVC + DVCLive + CML + AWS S3** for experiment tracking, data versioning, and CI/CD — built as a pilot project and template for radar ML applications.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  GitLab/     │     │  GitLab CI   │     │    AWS S3    │
│  GitHub Repo │────▶│  + CML       │────▶│  DVC Remote  │
│              │     │              │     │              │
│ src/         │     │ dvc pull     │     │ data/        │
│ configs/     │     │ dvc repro    │     │ models/      │
│ params.yaml  │     │ cml report   │     │              │
│ dvc.yaml     │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                     ┌──────▼──────┐
                     │ DVC Studio  │
                     │ Experiment  │
                     │ Dashboard   │
                     └─────────────┘
```

## Quick Start

### 1. Clone and setup
```bash
git clone <your-repo-url>
cd fashion-mnist-mlops
pip install -r requirements.txt
```

### 2. Initialize DVC (first time only)
```bash
dvc init
dvc remote add -d s3remote s3://your-bucket/fashion-mnist
dvc remote modify s3remote region eu-north-1
```

### 3. Run the pipeline
```bash
dvc repro                    # run all stages
```

### 4. Run experiments
```bash
# Compare architectures
dvc exp run -S train.arch_config=configs/simple_dense.yml
dvc exp run -S train.arch_config=configs/cnn_basic.yml
dvc exp run -S train.arch_config=configs/cnn_dropout.yml

# Compare learning rates
dvc exp run -S train.lr=0.01
dvc exp run -S train.lr=0.001
dvc exp run -S train.lr=0.0001

# Parallel sweep
dvc exp run --queue -S train.arch_config=configs/simple_dense.yml
dvc exp run --queue -S train.arch_config=configs/cnn_basic.yml
dvc exp run --queue -S train.arch_config=configs/cnn_dropout.yml
dvc queue start --jobs 3

# View results
dvc exp show
dvc exp diff <exp1> <exp2>
```

### 5. Push to S3
```bash
dvc push                     # push data + models to S3
git add . && git commit -m "experiment: cnn_basic lr=0.001"
git push
```

## Pipeline Stages

| Stage | Input | Output | What it does |
|-------|-------|--------|-------------|
| `preprocess` | Fashion MNIST (auto-download) | `data/processed/*.npy` | Normalize, reshape, split train/val/test |
| `train` | Processed data + arch config | `models/model.keras` | Build model from YAML, train, log with DVCLive |
| `evaluate` | Model + test data | `metrics/eval.json` | Accuracy, F1, confusion matrix, per-class report |

## Architecture Configs

| Config | Description | Expected Accuracy |
|--------|-------------|------------------|
| `configs/simple_dense.yml` | Flatten + Dense layers (baseline) | ~87% |
| `configs/cnn_basic.yml` | 2-layer CNN + MaxPool | ~91% |
| `configs/cnn_dropout.yml` | 3-layer CNN + BatchNorm + Dropout | ~92% |

## Project Structure

```
fashion-mnist-mlops/
├── configs/                  # Architecture definitions (1 YAML per arch)
│   ├── simple_dense.yml
│   ├── cnn_basic.yml
│   └── cnn_dropout.yml
├── src/                      # Source code
│   ├── preprocess.py         # Data loading + preprocessing
│   ├── builder.py            # YAML-driven model builder
│   ├── train.py              # Training + DVCLive logging
│   └── evaluate.py           # Evaluation + confusion matrix
├── data/processed/           # DVC-tracked processed data
├── models/                   # DVC-tracked trained models
├── metrics/                  # Evaluation metrics (git-tracked)
│   ├── eval.json
│   ├── confusion_matrix.csv
│   └── confusion_matrix.png
├── dvclive/                  # DVCLive training logs + plots
├── dvc.yaml                  # Pipeline definition
├── params.yaml               # Hyperparameters (DVC-tracked)
├── requirements.txt
└── README.md
```

## DVC Studio

Connect your repo at [studio.iterative.ai](https://studio.iterative.ai) to:
- Compare experiments visually
- Filter by architecture, learning rate, or any parameter
- View training curves and confusion matrices
- Share results with your team

## AWS S3 Setup

```bash
# Create bucket
aws s3 mb s3://your-bucket-name --region eu-north-1

# Configure DVC remote
dvc remote add -d s3remote s3://your-bucket-name/fashion-mnist
dvc remote modify s3remote region eu-north-1

# Push data and models
dvc push
```

## Transferring to Radar ML Project

This pipeline is designed as a template. To adapt for radar:

| This project | Radar project |
|-------------|--------------|
| Fashion MNIST images | Acconeer .h5 IQ data |
| `input_shape: (28, 28, 1)` | `input_shape: (40, 4, 3)` |
| 10 classes (clothing) | 3 classes (empty/occupied/child) |
| `preprocess.py` (normalize images) | `preprocess.py` (sliding window + IQ extraction) |
| Same `builder.py` | Same `builder.py` |
| Same `dvc.yaml` structure | Same `dvc.yaml` structure |
| Same `params.yaml` pattern | Same `params.yaml` pattern |
