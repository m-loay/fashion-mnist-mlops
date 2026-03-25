#!/usr/bin/env bash
# ============================================================
# scripts/aws_setup.sh
# One-shot AWS bootstrap for fashion-mnist-mlops DVC remote
#
# What it does:
#   1. Creates an S3 bucket in eu-north-1
#   2. Enables versioning on the bucket
#   3. Creates a dedicated IAM user (mlops-dvc-user)
#   4. Attaches a least-privilege S3 policy to that user
#   5. Creates an access key for the IAM user
#   6. Configures the DVC remote in your local repo
#   7. Prints the GitHub Secrets you need to set
#
# Prerequisites:
#   - AWS CLI installed and configured with an admin account
#     (aws configure  — or set AWS_ACCESS_KEY_ID / SECRET env vars)
#   - DVC installed (pip install dvc[s3])
#   - Run from the root of your repo
#
# Usage:
#   chmod +x scripts/aws_setup.sh
#   ./scripts/aws_setup.sh
#   ./scripts/aws_setup.sh --bucket my-custom-bucket-name
# ============================================================

set -euo pipefail

# ── Defaults (override via flags) ──────────────────────────
BUCKET_NAME="fashion-mnist-mlops-$(openssl rand -hex 4)"  # unique suffix
REGION="eu-north-1"
IAM_USER="mlops-dvc-user"
DVC_REMOTE_NAME="s3remote"
PREFIX="fashion-mnist"

# ── Argument parsing ───────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --bucket)    BUCKET_NAME="$2"; shift 2 ;;
    --region)    REGION="$2";      shift 2 ;;
    --iam-user)  IAM_USER="$2";    shift 2 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║         Fashion MNIST MLOps — AWS Bootstrap          ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Bucket  : s3://${BUCKET_NAME}"
echo "  Region  : ${REGION}"
echo "  IAM User: ${IAM_USER}"
echo ""

# ── Check AWS CLI is available ─────────────────────────────
if ! command -v aws &>/dev/null; then
  echo "❌ AWS CLI not found. Install it: https://aws.amazon.com/cli/"
  exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "✅ AWS account: ${AWS_ACCOUNT_ID}"
echo ""

# ══════════════════════════════════════════════════════════════
# STEP 1 — Create S3 bucket
# ══════════════════════════════════════════════════════════════
echo "─── Step 1: Creating S3 bucket ───────────────────────"

# eu-north-1 requires LocationConstraint (unlike us-east-1)
if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
  echo "ℹ️  Bucket ${BUCKET_NAME} already exists — skipping creation."
else
  aws s3api create-bucket \
    --bucket "${BUCKET_NAME}" \
    --region "${REGION}" \
    --create-bucket-configuration LocationConstraint="${REGION}"
  echo "✅ Bucket created: s3://${BUCKET_NAME}"
fi

# Enable versioning (allows DVC to track object history)
aws s3api put-bucket-versioning \
  --bucket "${BUCKET_NAME}" \
  --versioning-configuration Status=Enabled
echo "✅ Versioning enabled"

# Block all public access (security best practice)
aws s3api put-public-access-block \
  --bucket "${BUCKET_NAME}" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,\
BlockPublicPolicy=true,RestrictPublicBuckets=true
echo "✅ Public access blocked"
echo ""

# ══════════════════════════════════════════════════════════════
# STEP 2 — Create IAM user with least-privilege S3 policy
# ══════════════════════════════════════════════════════════════
echo "─── Step 2: Creating IAM user ────────────────────────"

# Create user (idempotent — ignore AlreadyExists)
aws iam create-user --user-name "${IAM_USER}" 2>/dev/null || \
  echo "ℹ️  IAM user ${IAM_USER} already exists — skipping."

# Write least-privilege policy (only this bucket)
POLICY_DOC=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DVCRemoteAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::${BUCKET_NAME}",
        "arn:aws:s3:::${BUCKET_NAME}/*"
      ]
    },
    {
      "Sid": "CMLRunnerEC2Access",
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:CreateTags",
        "ec2:DescribeImages",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeKeyPairs",
        "ec2:RequestSpotInstances",
        "ec2:CancelSpotInstanceRequests",
        "ec2:DescribeSpotInstanceRequests",
        "ec2:CreateSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:DescribeVpcs"
      ],
      "Resource": "*"
    }
  ]
}
EOF
)

POLICY_NAME="${IAM_USER}-policy"
POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"

# Create or update policy
if aws iam get-policy --policy-arn "${POLICY_ARN}" 2>/dev/null; then
  echo "ℹ️  Policy ${POLICY_NAME} already exists."
else
  aws iam create-policy \
    --policy-name "${POLICY_NAME}" \
    --policy-document "${POLICY_DOC}" \
    --description "Least-privilege policy for DVC S3 remote + CML EC2 runner"
  echo "✅ Policy created: ${POLICY_NAME}"
fi

# Attach policy to user
aws iam attach-user-policy \
  --user-name "${IAM_USER}" \
  --policy-arn "${POLICY_ARN}"
echo "✅ Policy attached to ${IAM_USER}"
echo ""

# ══════════════════════════════════════════════════════════════
# STEP 3 — Create access key for the IAM user
# ══════════════════════════════════════════════════════════════
echo "─── Step 3: Creating access key ──────────────────────"

KEY_JSON=$(aws iam create-access-key --user-name "${IAM_USER}")
ACCESS_KEY_ID=$(echo "${KEY_JSON}"     | python3 -c "import sys,json; print(json.load(sys.stdin)['AccessKey']['AccessKeyId'])")
SECRET_ACCESS_KEY=$(echo "${KEY_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['AccessKey']['SecretAccessKey'])")

echo "✅ Access key created"
echo ""

# ══════════════════════════════════════════════════════════════
# STEP 4 — Configure DVC remote
# ══════════════════════════════════════════════════════════════
echo "─── Step 4: Configuring DVC remote ───────────────────"

dvc remote add -d -f "${DVC_REMOTE_NAME}" "s3://${BUCKET_NAME}/${PREFIX}"
dvc remote modify "${DVC_REMOTE_NAME}" region "${REGION}"

echo "✅ DVC remote configured: ${DVC_REMOTE_NAME} → s3://${BUCKET_NAME}/${PREFIX}"
echo "   (settings saved to .dvc/config)"
echo ""

# ══════════════════════════════════════════════════════════════
# STEP 5 — Print GitHub Secrets instructions
# ══════════════════════════════════════════════════════════════
echo "╔══════════════════════════════════════════════════════╗"
echo "║   ⚠️  COPY THESE — they will NOT be shown again      ║"
echo "╠══════════════════════════════════════════════════════╣"
echo ""
echo "  Go to: https://github.com/m-loay/fashion-mnist-mlops"
echo "          → Settings → Secrets and variables → Actions"
echo "          → New repository secret"
echo ""
echo "  ┌─────────────────────────────────────────────────────"
echo "  │  Name : AWS_ACCESS_KEY_ID"
echo "  │  Value: ${ACCESS_KEY_ID}"
echo "  └─────────────────────────────────────────────────────"
echo ""
echo "  ┌─────────────────────────────────────────────────────"
echo "  │  Name : AWS_SECRET_ACCESS_KEY"
echo "  │  Value: ${SECRET_ACCESS_KEY}"
echo "  └─────────────────────────────────────────────────────"
echo ""
echo "  Optional (for DVC Studio experiment dashboard):"
echo "  ┌─────────────────────────────────────────────────────"
echo "  │  Name : DVCLIVE_STUDIO_TOKEN"
echo "  │  Value: <get from https://studio.iterative.ai>"
echo "  └─────────────────────────────────────────────────────"
echo ""
echo "╠══════════════════════════════════════════════════════╣"
echo "║   Next steps                                         ║"
echo "╠══════════════════════════════════════════════════════╣"
echo ""
echo "  1. Set the 3 GitHub Secrets above."
echo ""
echo "  2. Update params.yaml — set your bucket name:"
echo "     execution.dvc_remote.bucket: ${BUCKET_NAME}"
echo ""
echo "  3. Push your first data to S3:"
echo "     dvc push"
echo ""
echo "  4. Push to GitHub to trigger the pipeline:"
echo "     git add .dvc/config params.yaml"
echo "     git commit -m 'chore: configure S3 remote + params'"
echo "     git push"
echo ""
echo "  5. To run on cloud EC2 manually:"
echo "     GitHub → Actions → ML Pipeline → Run workflow"
echo "     → check 'Run on cloud EC2'"
echo ""
echo "╚══════════════════════════════════════════════════════╝"

# ── Save summary to a local file (credentials excluded) ──
cat > aws_setup_summary.txt <<SUMMARY
AWS Setup Summary
=================
Bucket   : s3://${BUCKET_NAME}
Region   : ${REGION}
IAM User : ${IAM_USER}
Policy   : ${POLICY_NAME}
DVC Remote: ${DVC_REMOTE_NAME} → s3://${BUCKET_NAME}/${PREFIX}

GitHub Secrets to set:
  AWS_ACCESS_KEY_ID     = ${ACCESS_KEY_ID}
  AWS_SECRET_ACCESS_KEY = (see terminal output — not saved here for security)

Setup completed: $(date)
SUMMARY

echo "📄 Summary (without secret key) saved to: aws_setup_summary.txt"
echo "   Add it to .gitignore!"
echo ""
