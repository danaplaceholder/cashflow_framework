FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ARG TARGETARCH
ARG D2_VERSION=v0.7.1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    librsvg2-bin \
    ffmpeg \
    && arch="$TARGETARCH" \
    && if [ -z "$arch" ]; then arch="$(dpkg --print-architecture)"; fi \
    && curl -fsSL "https://github.com/terrastruct/d2/releases/download/${D2_VERSION}/d2-${D2_VERSION}-linux-${arch}.tar.gz" \
       -o /tmp/d2.tar.gz \
    && mkdir -p /tmp/d2 \
    && tar -xzf /tmp/d2.tar.gz -C /tmp/d2 \
    && install -m 755 "$(find /tmp/d2 -type f -name d2 | head -n 1)" /usr/local/bin/d2 \
    && d2 --version \
    && rm -rf /tmp/d2 /tmp/d2.tar.gz /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --upgrade pip && pip install -e ".[dev]"

COPY tests/ ./tests/
COPY examples/ ./examples/

CMD ["bash"]
