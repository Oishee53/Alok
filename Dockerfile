# আলোক (Alok) — Hugging Face Spaces / any Docker host
# Spaces expects the app on port 7860, running as a non-root user.

FROM python:3.11-slim

# OpenCV runtime libraries
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    YOLO_CONFIG_DIR=/tmp/ultralytics

WORKDIR $HOME/app

# CPU-only torch first (the default CUDA build is ~5GB and useless here)
COPY --chown=user backend/requirements-deploy.txt .
RUN pip install --no-cache-dir --user torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --user -r requirements-deploy.txt

# App code + models + frontend
COPY --chown=user backend/ .
COPY --chown=user frontend/ ./frontend/

EXPOSE 7860
# Render (and similar hosts) assign their own port via $PORT and expect the
# app to bind to it; Hugging Face Spaces doesn't set it, so 7860 is the
# fallback. --workers 1 is explicit and load-bearing: a second worker would
# load a second full copy of both YOLO models, doubling memory on hosts
# that are already tight on RAM (e.g. Render's free 512MB tier).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
