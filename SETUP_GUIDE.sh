#!/bin/bash
# ============================================================
# SETUP GUIDE — Step-by-step commands
# ============================================================
# Run these commands in order to set up the full pipeline.
# ============================================================

# ─────────────────────────────────────────────────
# STEP 1: Create GitHub repo and clone
# ─────────────────────────────────────────────────
# Create a new repo on GitHub called "fashion-mnist-mlops"
# Then:
git clone https://github.com/YOUR_USERNAME/fashion-mnist-mlops.git
cd fashion-mnist-mlops
# Copy all project files into this directory

# ─────────────────────────────────────────────────
# STEP 2: Python environment
# ─────────────────────────────────────────────────
python -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows
pip install -r requirements.txt

# ─────────────────────────────────────────────────
# STEP 3: Initialize DVC
# ─────────────────────────────────────────────────
dvc init
git add .dvc .dvcignore
git commit -m "init: initialize DVC"

# ─────────────────────────────────────────────────
# STEP 4: AWS S3 setup
# ─────────────────────────────────────────────────
# 4a. Create free AWS account at https://aws.amazon.com/free/
#     (You get $200 in credits + 5GB S3 free tier)
#
# 4b. Install AWS CLI
pip install awscli
#
# 4c. Create IAM user with S3 access:
#     - Go to AWS Console → IAM → Users → Create User
#     - Attach policy: AmazonS3FullAccess
#     - Create access key (CLI type)
#
# 4d. Configure credentials
aws configure
#     AWS Access Key ID: <your-key>
#     AWS Secret Access Key: <your-secret>
#     Default region: eu-north-1  (Stockholm — closest to you)
#     Output format: json
#
# 4e. Create S3 bucket
aws s3 mb s3://fashion-mnist-mlops-YOUR_NAME --region eu-north-1
#
# 4f. Configure DVC remote
dvc remote add -d s3remote s3://fashion-mnist-mlops-YOUR_NAME/dvc-store
dvc remote modify s3remote region eu-north-1
git add .dvc/config
git commit -m "config: add S3 remote for DVC"

# ─────────────────────────────────────────────────
# STEP 5: Run pipeline locally (first time)
# ─────────────────────────────────────────────────
dvc repro

# This will:
#   1. preprocess: download Fashion MNIST, process, save .npy files
#   2. train: build CNN from configs/cnn_basic.yml, train 10 epochs
#   3. evaluate: compute metrics, save confusion matrix

# ─────────────────────────────────────────────────
# STEP 6: Push data and models to S3
# ─────────────────────────────────────────────────
dvc push

# Verify it's on S3:
aws s3 ls s3://fashion-mnist-mlops-YOUR_NAME/dvc-store/ --recursive | head

# ─────────────────────────────────────────────────
# STEP 7: Commit and push to GitHub
# ─────────────────────────────────────────────────
git add .
git commit -m "feat: initial pipeline with cnn_basic architecture"
git push origin main

# ─────────────────────────────────────────────────
# STEP 8: Connect DVC Studio
# ─────────────────────────────────────────────────
# 8a. Go to https://studio.iterative.ai
# 8b. Sign in with your GitHub account
# 8c. Click "Add a repository" → select fashion-mnist-mlops
# 8d. DVC Studio will automatically detect your experiments
#
# You should now see your first experiment in the dashboard!

# ─────────────────────────────────────────────────
# STEP 9: Run architecture comparison experiments
# ─────────────────────────────────────────────────
# Experiment 1: Simple dense (baseline)
dvc exp run -S train.arch_config=configs/simple_dense.yml
git add . && git commit -m "exp: simple_dense baseline"

# Experiment 2: CNN basic
dvc exp run -S train.arch_config=configs/cnn_basic.yml
git add . && git commit -m "exp: cnn_basic"

# Experiment 3: CNN with dropout
dvc exp run -S train.arch_config=configs/cnn_dropout.yml
git add . && git commit -m "exp: cnn_dropout"

# Push experiments and data
dvc push
git push

# ─────────────────────────────────────────────────
# STEP 10: View experiments in DVC Studio
# ─────────────────────────────────────────────────
# Refresh DVC Studio — you should see 3 experiments with:
#   - arch_config column (filterable)
#   - test_accuracy, test_f1 metrics
#   - Training curves (loss, accuracy per epoch)
#   - Confusion matrix plots

# Compare in terminal:
dvc exp show --sort-by metrics/eval.json:test_accuracy

# ─────────────────────────────────────────────────
# STEP 11: Test reproducibility (optional but powerful demo)
# ─────────────────────────────────────────────────
# Delete local data and model
rm -rf data/processed/ models/

# Restore from S3
dvc pull

# Re-run pipeline — should produce identical results
dvc repro

# ─────────────────────────────────────────────────
# STEP 12: Parallel hyperparameter sweep
# ─────────────────────────────────────────────────
dvc exp run --queue -S train.lr=0.01 -S train.arch_config=configs/cnn_basic.yml
dvc exp run --queue -S train.lr=0.001 -S train.arch_config=configs/cnn_basic.yml
dvc exp run --queue -S train.lr=0.0001 -S train.arch_config=configs/cnn_basic.yml
dvc queue start --jobs 3

# View all results
dvc exp show
