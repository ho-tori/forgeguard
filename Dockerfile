FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FORGEGUARD_API_KEY_FILE=/run/secrets/forgeguard_api_key

WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY setup.py README.md ./
COPY forgeguard ./forgeguard
COPY config.docker.json ./config.docker.json
RUN pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 forgeguard \
    && mkdir -p /workspace \
    && chown forgeguard:forgeguard /workspace

USER forgeguard
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)" || exit 1

ENTRYPOINT ["forgeguard", "--workspace", "/workspace", "--config", "/app/config.docker.json"]
CMD ["serve", "--bind", "0.0.0.0", "--port", "8080", "--admin-token-file", "/run/secrets/forgeguard_admin_token"]
