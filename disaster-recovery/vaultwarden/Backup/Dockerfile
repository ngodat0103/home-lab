
FROM docker.io/astral/uv:0.9.3-python3.12-trixie AS builder
ENV UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./

# --frozen: strict sync from lockfile
# --no-install-project: minimal install (deps only)
RUN uv sync --frozen --no-install-project

FROM python:3.12-slim-trixie

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        lsb-release && \
    install -d /usr/share/postgresql-common/pgdg && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg && \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg] http://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client-16 && \
    apt-get purge -y --auto-remove curl gnupg lsb-release && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY --chmod=744 \
    backup.py \
    backup_db.py \
    backup_data.py \
    restore.py \
    logger_config.py \
    ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
LABEL org.opencontainers.image.source = "https://github.com/ngodat0103/home-lab"
CMD ["python", "backup.py"]