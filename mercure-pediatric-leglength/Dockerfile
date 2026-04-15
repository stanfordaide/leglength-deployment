# CUDA 12.1 + cuDNN 8 runtime on Ubuntu 22.04
# Python 3.12 is installed below via the deadsnakes PPA
# Use --platform=linux/arm64 for Apple Silicon Macs, or remove --platform for auto-detection
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# Environment variables for better container behavior
# Limit CPU threads to reduce I/O thrashing on NAS (OMP/MKL used by PyTorch)
ENV OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    TORCH_HOME=/app/v0/.cache \
    # PyTorch 2.x cache directory - bypasses getpwuid() lookup that fails with unknown UIDs
    TORCHINDUCTOR_CACHE_DIR=/tmp/torch_inductor_cache \
    # Fallback home directory for any user
    HOME=/app/v0

# Home directory setup
ENV HOME_DIR=/app/v0
RUN mkdir -p ${HOME_DIR}

# Set the working directory
# Note: This is the directory where the gear is run
WORKDIR ${HOME_DIR}

# Create non-root user for security
RUN groupadd -r mercureapp && useradd -r -g mercureapp -d ${HOME_DIR} -s /bin/bash mercureapp

# 1. Install software-properties-common to add deadsnakes PPA for Python 3.12
# 2. Install Python 3.12 and system dependencies
# 3. Bootstrap pip for Python 3.12 and set it as the default python3/pip3
# 4. Clean up package manager cache to reduce image size
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y \
        software-properties-common \
        && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update -qq && \
    apt-get install --no-install-recommends -y \
        python3.12 \
        python3.12-dev \
        python3.12-venv \
        git \
        wget \
        curl \
        ca-certificates \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1 \
        gosu \
        && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Upgrade pip and install Python dependencies
COPY requirements.txt ${HOME_DIR}/requirements.txt
RUN python3.12 -m pip install --upgrade pip setuptools wheel && \
    python3.12 -m pip install -r requirements.txt

# Create models and cache directories
RUN mkdir -p ${HOME_DIR}/models ${HOME_DIR}/.cache

# Copy only the files needed for downloading models first
# This layer will be cached unless download_models.py or registry.json change
COPY registry.json ${HOME_DIR}/registry.json
COPY download_models.py ${HOME_DIR}/download_models.py

# Download all model checkpoints
# Note: Comment out if you want to download models at runtime instead
RUN python3 download_models.py

# Copy the remaining application files
# This layer will be invalidated when application code changes, but models won't be re-downloaded
COPY leglength ${HOME_DIR}/leglength
COPY monitoring ${HOME_DIR}/monitoring
COPY run.py ${HOME_DIR}/run.py
COPY docker_entrypoint.sh ${HOME_DIR}/docker_entrypoint.sh

# Create output directory with proper permissions for volume mounting
RUN mkdir -p /output && \
    chown mercureapp:mercureapp /output && \
    chmod 755 /output

# Set proper ownership and permissions
RUN chown -R mercureapp:mercureapp ${HOME_DIR} && \
    chmod a+x ${HOME_DIR}/run.py && \
    chmod a+x ${HOME_DIR}/docker_entrypoint.sh

# Add health check to verify container readiness
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)" || exit 1

# Don't switch users here - let the entrypoint handle it
# This allows the entrypoint to fix permissions as root if needed
# USER mercureapp

# Add labels for better container management
LABEL maintainer="Arogya Koirala" \
      description="Leg Length Analysis Module" \
      version="1.0" \
      org.opencontainers.image.title="mercure-leglength" \
      org.opencontainers.image.description="Mercure processing module for leg length analysis"

# Configure entrypoint with proper signal handling
ENTRYPOINT ["./docker_entrypoint.sh"]