# syntax=docker/dockerfile:1

FROM python:3.13-slim

# uv: fast, reproducible installs from the committed uv.lock
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first (cached unless the lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Then the application code
COPY . .
RUN uv sync --frozen --no-dev

# App listens on this port inside the container; Traefik fronts it.
# Give Dokploy this number (or whatever PORT you set) in the Domain config.
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
