# =============================================================
# Dockerfile
# Location: docker/Dockerfile
#
# Slim ML training environment image.
# Contains ONLY: Python 3.12, CML, git, nodejs, npm.
# ALL Python packages including DVC, DVCLive, TensorFlow etc.
# are installed at runtime via pip install -r requirements.txt
# in train.yml. This keeps the image small for fast EC2 pulls.
# =============================================================

FROM python:3.12-slim-bookworm

# Label links this image to your GitHub repository.
LABEL org.opencontainers.image.source="https://github.com/m-loay/fashion-mnist-mlops"

# Apply security patches + install system dependencies
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

# Upgrade pip only
RUN pip install --no-cache-dir --upgrade pip

WORKDIR /workspace