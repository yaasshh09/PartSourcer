# PartSourcer backend — shared image for Render and Fly.io.
# Both hosts build this same Dockerfile; host-specific config lives in
# render.yaml / fly.toml. Python 3.11+ per project requirement.
FROM python:3.12-slim

# Faster, quieter Python in a container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install deps first so the layer caches across code-only changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source.
COPY . .

# Render injects PORT; Fly binds the internal_port from fly.toml. Default 8000
# covers local `docker run` and Fly (which does not set PORT automatically).
ENV PORT=8000
EXPOSE 8000

# Shell form so ${PORT} expands. Bind all interfaces for the platform proxy.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
