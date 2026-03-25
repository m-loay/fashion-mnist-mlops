# Cloud Setup Guide — fashion-mnist-mlops

Complete walkthrough to wire up AWS S3 (DVC remote), CML EC2 runners, and GitHub CI.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub Repo                                                │
│  ├── src/ configs/ params.yaml dvc.yaml                     │
│  └── .github/workflows/train.yml                            │
└───────────────┬─────────────────────────────────────────────┘
                │  git push / PR / manual dispatch
                ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions                                             │
│                                                             │
│  Job 1: setup                                               │
│  ├── run_on_cloud=false → runner-label = ubuntu-latest      │
│  └── run_on_cloud=true  → launch EC2 via CML                │
│                             └── runner-label = cml-ec2      │
│                                                             │
│  Job 2: train  (runs on the selected runner)                │
│  ├── pip install                                            │
│  ├── dvc pull  (from S3)                                    │
│  ├── dvc repro (run pipeline)                               │
│  ├── dvc push  (back to S3)                                 │
│  └── cml comment (post report to PR)                        │
└───────┬─────────────────────────┬───────────────────────────┘
        │                         │
        ▼                         ▼
┌───────────────┐       ┌─────────────────────┐
│  AWS S3       │       │  EC2 (spot)          │
│  DVC Remote   │       │  Self-hosted runner  │
│               │       │  (only when cloud)   │
│  data/        │       │  t3.xlarge / g4dn    │
│  models/      │       └─────────────────────┘
│  run-cache/   │
└───────────────┘
```

**Local path** (default, every push/PR): runs on the free GitHub-hosted runner.  
**Cloud path** (manual trigger): CML provisions a spot EC2 in eu-north-1, runs the full pipeline there, then the instance auto-terminates.

---

## Step 1 — AWS Account Setup

### 1.1 Create AWS account (skip if you have one)

1. Go to https://aws.amazon.com and click **Create an AWS Account**.
2. Follow the signup wizard — you'll need a credit card (Free Tier available).
3. After signup, go to the **IAM** service and create an **admin user** for yourself
   (never use the root account for daily work).

### 1.2 Install and configure the AWS CLI

```bash
# Install (macOS)
brew install awscli

# Install (Linux)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install

# Configure with your admin credentials
aws configure
# AWS Access Key ID:     <your admin key>
# AWS Secret Access Key: <your admin secret>
# Default region name:   eu-north-1
# Default output format: json
```

### 1.3 Run the bootstrap script

This script creates the S3 bucket, IAM user, policy, and configures DVC — all in one shot.

```bash
# From repo root
chmod +x scripts/aws_setup.sh
./scripts/aws_setup.sh

# Or with a specific bucket name
./scripts/aws_setup.sh --bucket fashion-mnist-mlops-prod
```

The script will print the two GitHub Secrets at the end. Copy them immediately — the secret key is only shown once.

---

## Step 2 — Configure GitHub Secrets

Go to your repo on GitHub:  
**Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value | Purpose |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | from script output | DVC S3 pull/push + CML EC2 |
| `AWS_SECRET_ACCESS_KEY` | from script output | DVC S3 pull/push + CML EC2 |
| `DVCLIVE_STUDIO_TOKEN` | from studio.iterative.ai | Experiment dashboard (optional) |

> **Why one IAM user for both S3 and EC2?**  
> The policy in the script grants only the minimum needed:
> S3 access on your specific bucket + EC2 permissions scoped to launching and terminating instances. No admin access is granted.

---

## Step 3 — First DVC Push

With the S3 bucket created and DVC configured, push your first dataset and models:

```bash
# Make sure you have data locally (run pipeline once)
dvc repro

# Push data + models + run cache to S3
dvc push

# Commit the updated .dvc/config
git add .dvc/config params.yaml .gitignore
git commit -m "chore: configure S3 remote (eu-north-1)"
git push
```

Verify the push worked:
```bash
aws s3 ls s3://YOUR-BUCKET-NAME/fashion-mnist/ --recursive --human-readable
```

---

## Step 4 — GitHub Actions CI

The workflow is already in `.github/workflows/train.yml`. Here is how each trigger works:

### Auto-trigger (push / PR)
Every push to `main` or PR touching `src/`, `configs/`, `params.yaml`, or `dvc.yaml` will automatically:
1. Pull data from S3 (`dvc pull`)
2. Reproduce any changed stages (`dvc repro`)
3. Push results back to S3 (`dvc push`)
4. Post a metrics + plots report as a PR comment

This runs on **GitHub-hosted runners** (free, 2 vCPU / 7 GB RAM). Fine for Fashion MNIST.

### Manual trigger — local runner
Go to **Actions → ML Pipeline → Run workflow** and leave `run_on_cloud` unchecked. Same as auto-trigger but you can specify it manually.

### Manual trigger — cloud EC2 runner
1. Go to **Actions → ML Pipeline → Run workflow**
2. Check **Run pipeline on a cloud EC2 instance**
3. Select instance type (e.g. `g4dn.xlarge` for GPU)
4. Optionally uncheck Spot if you need guaranteed availability

The workflow will:
- Provision a spot EC2 instance in eu-north-1 via CML
- Register it as a self-hosted GitHub runner with label `cml-ec2`
- Run the full DVC pipeline on that machine
- Push results to S3
- Post a report to GitHub
- Terminate the EC2 instance when done (idle-timeout = 1h)

---

## Step 5 — Controlling Local vs Cloud in params.yaml

The `execution` section in `params.yaml` documents your intent, but the actual switch at runtime is the `workflow_dispatch` input in GitHub Actions (or you can script it locally).

### Locally override pipeline execution

```bash
# Run pipeline locally (default)
dvc repro

# Run a single experiment with a different arch on the local machine
dvc exp run -S train.arch_config=configs/cnn_dropout.yml

# Trigger cloud training via GitHub CLI (no browser needed)
gh workflow run train.yml \
  --field run_on_cloud=true \
  --field instance_type=g4dn.xlarge \
  --field spot_instance=true
```

### params.yaml execution section

```yaml
execution:
  runner: local        # document intent — actual switch is in CI inputs
  cloud:
    instance_type: t3.xlarge
    spot: true
    region: eu-north-1
```

This section is version-controlled so you can track infrastructure choices alongside model changes. To run the same `dvc exp run` sweep on a GPU instance, update `instance_type: g4dn.xlarge`, commit, and trigger manually.

---

## Step 6 — Understanding the CML Report

After each pipeline run, CML posts a comment on the PR (or on the commit for direct pushes) that includes:

- **Metrics table** — accuracy, F1, loss from `metrics/eval.json`
- **Metrics diff** — how this run compares to `main` branch
- **Confusion matrix** — from `metrics/confusion_matrix.png`
- **Training curves** — accuracy and loss over epochs
- **DVCLive step plots** — live train/val curves from the `dvclive/` folder

Example of what you'll see on a PR:

```
## 📊 ML Pipeline Report
🖥️ Runner: GitHub-hosted (ubuntu-latest)

### 📈 Evaluation Metrics
| Metric   | Value  |
|----------|--------|
| accuracy | 0.9187 |
| f1_macro | 0.9181 |

### 🔀 Metrics vs main
| Metric   | main   | branch | Δ      |
|----------|--------|--------|--------|
| accuracy | 0.9103 | 0.9187 | +0.0084|
```

---

## Cost Reference (eu-north-1 spot prices, approximate)

| Instance | vCPU | RAM | GPU | Spot $/hr | Fashion MNIST run |
|---|---|---|---|---|---|
| t3.xlarge | 4 | 16 GB | — | ~$0.04 | ~$0.01 |
| m5.xlarge | 4 | 16 GB | — | ~$0.06 | ~$0.015 |
| c5.2xlarge | 8 | 16 GB | — | ~$0.09 | ~$0.015 |
| g4dn.xlarge | 4 | 16 GB | T4 | ~$0.16 | ~$0.03 |
| g4dn.2xlarge | 8 | 32 GB | T4 | ~$0.28 | ~$0.05 |

S3 storage: ~$0.023/GB/month. A full Fashion MNIST dataset + models is < 1 GB → < $0.03/month.

The `--idle-timeout=3600` setting in the workflow ensures the EC2 instance terminates after 1 hour of inactivity even if the job crashes, preventing runaway costs.

---

## Troubleshooting

**`dvc push` permission denied**  
→ Check that `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` secrets are set correctly in GitHub.  
→ Run `aws sts get-caller-identity` locally to verify your CLI credentials.

**EC2 runner never picks up the job**  
→ The `cml runner launch ... &` command runs in the background. Allow 2–3 minutes for EC2 to boot and register.  
→ Check the EC2 console in eu-north-1 for a running instance tagged `cml`.

**Spot instance interrupted mid-run**  
→ Uncheck `spot_instance` in the workflow dispatch inputs. On-demand instances won't be interrupted.

**`dvc repro` re-runs everything even when unchanged**  
→ Make sure `dvc.lock` is committed. If the lock file is in `.gitignore`, DVC can't detect what's up-to-date.

**CML report missing plots**  
→ The evaluate stage must complete successfully for `metrics/confusion_matrix.png` to exist.  
→ Check the GitHub Actions log for the `evaluate` stage output.
