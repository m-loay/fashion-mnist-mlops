# =============================================================
# Dockerfile
# Location: docker/Dockerfile  (create this folder in your repo)
#
# Custom ML training image based on Python 3.12.
# Contains all project dependencies pre-installed.
# Pushed to ghcr.io and used as the container in train.yml.
#
# Built automatically by .github/workflows/build-image.yml
# whenever requirements.txt or this Dockerfile changes.
# =============================================================

FROM python:3.12-slim-bookworm

# Label links this image to your GitHub repository.
# Required for GITHUB_TOKEN to have push permission to ghcr.io.
LABEL org.opencontainers.image.source="https://github.com/m-loay/fashion-mnist-mlops"

# Apply all security patches first, then install system dependencies.
# apt-get upgrade eliminates critical/high CVEs in base Debian packages.
# Install system dependencies:
#   git     — required by DVC and CML
#   curl    — required by CML publish (image upload)
#   nodejs  — required by CML
#   npm     — required by CML
#   libgomp1 — required by scikit-learn
RUN apt-get update -y -q && \
    apt-get upgrade -y -q && \
    apt-get install -y -q --no-install-recommends \
        git \
        curl \
        nodejs \
        npm \
        libgomp1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install CML CLI via npm
RUN npm install -g @dvcorg/cml

# Copy and install Python requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /workspace