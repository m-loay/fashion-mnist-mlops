# MLOps Setup Guide — AWS + IAM + DVC + GitHub CI

This guide covers everything you need to do **once** to wire up the full pipeline.
After this guide, every push to `main` (or PR targeting `main`) will automatically
train on AWS EC2 and post a metrics report to GitHub.

---

## What is manual vs automated

| Task | How |
|---|---|
| Create AWS account | Manual — no way to automate |
| Create IAM user + attach policies | Manual in AWS Console |
| Install AWS CLI | Manual on your machine |
| Run `aws configure` | Manual on your machine |
| Create S3 bucket + configure DVC | **Automated** — `scripts/aws_setup.sh` |
| Set GitHub Secrets | Manual — 2 copy-pastes |

---

## Step 1 — Create AWS account

1. Go to https://aws.amazon.com and click **Create an AWS Account**
2. Fill in email, password, account name
3. Choose **Personal** account type
4. Enter credit card (required even for free tier — you won't be charged for small usage)
5. Verify phone number
6. Select **Basic support (Free)**
7. Sign in to the console at https://console.aws.amazon.com

> **Cost expectation for this project:** Running Fashion MNIST on a `t3.medium` spot
> instance costs roughly $0.01–$0.02 per training run. S3 storage for the dataset
> and models is less than $0.05/month.

---

## Step 2 — Create IAM user

This creates a dedicated user for this project so you never use your root account
for programmatic access.

### 2.1 Open IAM

In the AWS Console search bar type **IAM** → click **IAM** → click **Users** in
the left sidebar → click **Create user**

### 2.2 User details

- **User name:** `mlops-dvc-user` (or any name you prefer)
- Leave "Provide user access to the AWS Management Console" **unchecked**
- Click **Next**

### 2.3 Set permissions

- Select **Attach policies directly**
- Search and check **`AmazonS3FullAccess`**
- Search and check **`AmazonEC2FullAccess`**
- Click **Next** → **Create user**

### 2.4 Create access key

- Click into the user you just created
- Click the **Security credentials** tab
- Scroll to **Access keys** → click **Create access key**
- Select **Application running outside AWS** → click **Next** → **Create access key**
- **Copy both values now** — the secret key is only shown once:

```
Access key ID:     AKIA...............
Secret access key: ........................................
```

Save them somewhere safe temporarily — you will need them in Step 3 and Step 5.

---

## Step 3 — Install AWS CLI and configure it

### 3.1 Install (Windows)

Download and run:
```
https://awscli.amazonaws.com/AWSCLIV2.msi
```
Next → Next → Finish. No options to change.

### 3.2 Verify (open Git Bash)

```bash
aws --version
# Expected: aws-cli/2.x.x Python/3.x.x Windows/...
```

### 3.3 Configure with your IAM credentials

```bash
aws configure
```

Enter exactly:
```
AWS Access Key ID:     <your access key ID from step 2.4>
AWS Secret Access Key: <your secret access key from step 2.4>
Default region name:   eu-north-1
Default output format: json
```

### 3.4 Verify connection

```bash
aws sts get-caller-identity
```

Expected output:
```json
{
    "UserId": "AIDA...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/mlops-dvc-user"
}
```

If this prints your account info, the CLI is working correctly.

---

## Step 4 — Run aws_setup.sh

This script creates the S3 bucket and configures the DVC remote.
It assumes Steps 1–3 are complete.

```bash
# From your repo root in Git Bash
chmod +x scripts/aws_setup.sh
./scripts/aws_setup.sh
```

The script will:
- Create the S3 bucket `fashion-mnist-mlops` in `eu-north-1`
- Enable versioning on the bucket
- Block public access
- Configure DVC remote to point at the bucket
- Commit `.dvc/config` automatically

If you want a different bucket name:
```bash
./scripts/aws_setup.sh --bucket my-custom-name
```

---

## Step 5 — Set GitHub Secrets

Go to your repo on GitHub:
**Settings → Secrets and variables → Actions → New repository secret**

Add these two secrets — the values are the same keys from Step 2.4:

| Secret name | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | your access key ID |
| `AWS_SECRET_ACCESS_KEY` | your secret access key |

---

## Step 6 — First DVC push

Run the pipeline once locally to generate data and models, then push to S3:

```bash
# In Git Bash from repo root
pip install -r requirements.txt

dvc repro          # runs all 4 stages: load_data, preprocess, train, evaluate
dvc push           # uploads data + models to S3
```

Verify the upload worked:
```bash
aws s3 ls s3://fashion-mnist-mlops/fashion-mnist/ --recursive --human-readable
```

---

## Step 7 — Push to GitHub and watch CI run

```bash
git add .
git commit -m "feat: add cloud CI pipeline"
git push origin main
```

Go to your repo → **Actions** tab → watch the **ML Pipeline** workflow run.
It will:
1. Provision a spot EC2 `t3.medium` in `eu-north-1` via CML
2. Pull data from S3
3. Run `dvc repro` on the cloud instance
4. Push results back to S3
5. Post a metrics report as a commit comment

---

## How CI triggers work

| Action | Triggers CI? |
|---|---|
| Push to `main` | Yes — runs on cloud |
| PR from any branch → `main` | Yes — runs on cloud, posts report to PR |
| Push to `feature/*` or any other branch | **No** |
| Manual trigger (Actions → Run workflow) | Yes — choose instance type |

---

## Local training (no cloud)

To train on your local machine, change `params.yaml`:

```yaml
load_data:
  source: download   # downloads Fashion MNIST automatically
  # or:
  source: local
  local_path: C:/Users/you/datasets/fashion-mnist   # your local path
```

Then run:
```bash
dvc repro
```

This does not touch AWS or trigger any CI. Results stay local until you `dvc push`.

---

## Troubleshooting

**`aws: command not found` in Git Bash**
→ Close and reopen Git Bash after installing the MSI. The PATH update needs a fresh shell.

**`dvc push` access denied**
→ Run `aws sts get-caller-identity` to confirm credentials are correct.
→ Confirm the bucket name in `.dvc/config` matches what was created.

**CML runner never starts**
→ Check the `deploy-runner` job logs in GitHub Actions — CML logs the EC2 instance ID.
→ Check EC2 console in `eu-north-1` for a running instance tagged `cml`.

**Spot instance interrupted**
→ Re-run the workflow from GitHub Actions. Spot interruptions are rare for `t3.medium`.
→ For a guaranteed run: edit the workflow and remove `--cloud-spot` from the CML command.

**`dvc repro` re-runs everything even when nothing changed**
→ Confirm `dvc.lock` is committed to git. If it's in `.gitignore`, DVC cannot detect
  what is already up to date.