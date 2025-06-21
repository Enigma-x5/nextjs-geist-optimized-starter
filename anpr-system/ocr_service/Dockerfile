# Build stage
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04 as builder

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install Python and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-dev \
    python3-pip \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python packages
COPY requirements.txt .
RUN pip3 install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV FLAGS_allocator_strategy=naive_best_fit
ENV FLAGS_fraction_of_gpu_memory_to_use=0.1
ENV CUDA_VISIBLE_DEVICES=0

# Install Python and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create model directory and download PaddleOCR models
RUN mkdir -p /root/.paddleocr

# Create non-root user
RUN useradd -m -r service && \
    chown -R service:service /app /root/.paddleocr

USER service

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python3 -c "from paddleocr import PaddleOCR; PaddleOCR(use_gpu=True).get_version()"

# Set default command
CMD ["python3", "main.py"]
