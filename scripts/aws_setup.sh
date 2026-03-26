#!/usr/bin/env bash
# =============================================================
# scripts/aws_setup.sh
#
# PURPOSE:
#   Creates the S3 bucket and configures the DVC remote.
#
# PREREQUISITES (must be done manually before running this):
#   1. AWS account exists
#   2. IAM user created with AmazonS3FullAccess + AmazonEC2FullAccess
#   3. Access key created for that IAM user
#   4. AWS CLI installed  (https://awscli.amazonaws.com/AWSCLIV2.msi on Windows)
#   5. `aws configure` run with the IAM user's credentials
#   6. DVC installed  (pip install "dvc[s3]")
#
# USAGE:
#   chmod +x scripts/aws_setup.sh
#   ./scripts/aws_setup.sh
#   ./scripts/aws_setup.sh --bucket my-custom-bucket-name
#
# Run from the root of your repo (where dvc.yaml lives).
# =============================================================

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────
BUCKET_NAME="fashion-mnist-mlops"
REGION="eu-north-1"
DVC_REMOTE_NAME="s3remote"
PREFIX="fashion-mnist"

# ── Argument parsing ──────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --bucket) BUCKET_NAME="$2"; shift 2 ;;
    --region) REGION="$2";      shift 2 ;;
    *) echo "Unknown flag: $1. Usage: ./aws_setup.sh [--bucket NAME] [--region REGION]"; exit 1 ;;
  esac
done

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     Fashion MNIST MLOps — S3 + DVC Setup             ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Bucket : s3://${BUCKET_NAME}/${PREFIX}"
echo "  Region : ${REGION}"
echo ""

# ── Check 1: AWS CLI available ────────────────────────────────
echo "─── Checking AWS CLI ──────────────────────────────────"

if ! command -v aws &>/dev/null; then
  echo ""
  echo "ERROR: AWS CLI not found."
  echo "Install from: https://awscli.amazonaws.com/AWSCLIV2.msi"
  echo "Then run:     aws configure"
  exit 1
fi

# ── Check 2: credentials work ─────────────────────────────────
if ! aws sts get-caller-identity &>/dev/null; then
  echo ""
  echo "ERROR: AWS credentials not configured or invalid."
  echo "Run: aws configure"
  echo "Enter your IAM user's Access Key ID and Secret Access Key."
  exit 1
fi

CALLER=$(aws sts get-caller-identity --output text --query 'Arn')
echo "✅ Authenticated as: ${CALLER}"
echo ""

# ── Check 3: DVC available ────────────────────────────────────
echo "─── Checking DVC ──────────────────────────────────────"

if ! command -v dvc &>/dev/null; then
  echo "DVC not found — installing dvc[s3]..."
  pip install "dvc[s3]" --quiet
fi
echo "✅ DVC $(dvc --version)"
echo ""

# ── Step 1: create S3 bucket ──────────────────────────────────
echo "─── Step 1: S3 bucket ─────────────────────────────────"

if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
  echo "ℹ️  Bucket '${BUCKET_NAME}' already exists — skipping."
else
  # eu-north-1 requires LocationConstraint (only us-east-1 is exempt)
  aws s3api create-bucket \
    --bucket "${BUCKET_NAME}" \
    --region "${REGION}" \
    --create-bucket-configuration LocationConstraint="${REGION}"
  echo "✅ Bucket created: s3://${BUCKET_NAME}"
fi

# ── Step 2: enable versioning ─────────────────────────────────
aws s3api put-bucket-versioning \
  --bucket "${BUCKET_NAME}" \
  --versioning-configuration Status=Enabled
echo "✅ Versioning enabled"

# ── Step 3: block public access ───────────────────────────────
aws s3api put-public-access-block \
  --bucket "${BUCKET_NAME}" \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
echo "✅ Public access blocked"
echo ""

# ── Step 4: configure DVC remote ─────────────────────────────
echo "─── Step 4: DVC remote ────────────────────────────────"

# -f overwrites an existing remote with the same name
dvc remote add -d -f "${DVC_REMOTE_NAME}" "s3://${BUCKET_NAME}/${PREFIX}"
dvc remote modify "${DVC_REMOTE_NAME}" region "${REGION}"

echo "✅ DVC remote '${DVC_REMOTE_NAME}' → s3://${BUCKET_NAME}/${PREFIX}"
echo ""

# ── Step 5: commit .dvc/config ───────────────────────────────
echo "─── Step 5: Committing config ─────────────────────────"

git add .dvc/config
if git diff --staged --quiet; then
  echo "ℹ️  .dvc/config unchanged — nothing to commit."
else
  git commit -m "chore: configure S3 DVC remote (${REGION})"
  echo "✅ .dvc/config committed"
fi
echo ""

# ── Done ──────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Done. Remaining manual steps:                       ║"
echo "╠══════════════════════════════════════════════════════╣"
echo ""
echo "  1. Add 2 secrets to GitHub:"
echo "     Repo → Settings → Secrets and variables → Actions"
echo ""
echo "       Name: AWS_ACCESS_KEY_ID"
echo "       Value: (your IAM access key ID)"
echo ""
echo "       Name: AWS_SECRET_ACCESS_KEY"
echo "       Value: (your IAM secret access key)"
echo ""
echo "  2. Push data to S3 for the first time:"
echo "       dvc repro    # run pipeline locally once"
echo "       dvc push     # upload data + models to S3"
echo ""
echo "  3. Trigger cloud training:"
echo "       git push origin main"
echo ""
echo "╚══════════════════════════════════════════════════════╝"