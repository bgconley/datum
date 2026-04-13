# Qwen3-Embedder - PyTorch CUDA Dockerfile
# Multi-stage build for optimized image size

# ==============================================================================
# Stage 1: Builder
# ==============================================================================
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS builder

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and build dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create venv
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip wheel setuptools

# Install PyTorch with CUDA support
RUN pip install torch --index-url https://download.pytorch.org/whl/cu124

# Install Flash Attention 2 (requires CUDA dev tools)
RUN pip install flash-attn --no-build-isolation

# Copy and install application
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/

RUN pip install -e ".[cuda]"

# ==============================================================================
# Stage 2: Runtime
# ==============================================================================
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS runtime

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python runtime only
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application
WORKDIR /app
COPY --from=builder /app/src /app/src
COPY --from=builder /app/config /app/config
COPY --from=builder /app/pyproject.toml /app/

# Environment configuration
ENV QWEN_EMBED_BACKEND=pytorch
ENV QWEN_EMBED_PROFILE=qwen3_4b_cuda
ENV QWEN_EMBED_HOST=0.0.0.0
ENV QWEN_EMBED_PORT=8010
ENV QWEN_EMBED_LOG_FORMAT=json
ENV PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# HuggingFace cache directory
ENV HF_HOME=/app/.cache/huggingface
RUN mkdir -p /app/.cache/huggingface

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

# Expose port
EXPOSE 8010

# Run the service
CMD ["python", "-m", "qwen3_embedder.main"]
