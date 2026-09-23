# syntax=docker/dockerfile:1
# ---- Python deps ------------------------------------------------------------
FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock /app/
# Deps only (virtual project) in their own layer: source edits don't reinstall them.
RUN uv sync --frozen --no-dev
# [help]
# Built with uvx so the docs generator never enters the app's dependency tree.
COPY zensical.toml /app/
COPY help /app/help
RUN uvx zensical build
# [/help]

# ---- CSS (Tailwind standalone, no Node) --------------------------------------
FROM debian:bookworm-slim AS css
ARG TAILWIND_VERSION=v4.1.13
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN arch=$([ "$TARGETARCH" = "arm64" ] && echo arm64 || echo x64) \
 && curl -sSLf -o /usr/local/bin/tailwindcss \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/tailwindcss-linux-${arch}" \
 && chmod +x /usr/local/bin/tailwindcss
COPY static /app/static
COPY templates /app/templates
COPY src /app/src
RUN tailwindcss -i static/css/input.css -o static/css/output.css --minify

# ---- Runtime ----------------------------------------------------------------
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/src"
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}
WORKDIR /app
# curl: HEALTHCHECK. libpq5: psycopg. Add runtime libs here with a comment saying which feature needs them.
RUN apt-get update && apt-get install -y --no-install-recommends curl libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
COPY . /app/
COPY --from=css /app/static/css/output.css /app/static/css/output.css
# [help]
COPY --from=builder /app/help_site /app/help_site
# [/help]
# Dummy values exist only for this RUN line: settings refuse to boot without real secrets.
# --ignore input.css: the Tailwind source's @import breaks manifest post-processing.
RUN SECRET_KEY=build-only DEBUG=false \
    DATABASE_URL=postgres://build:build@localhost/build \
    # [tenant]
    ADMIN_DATABASE_URL=postgres://build:build@localhost/build \
    # [/tenant]
    python manage.py collectstatic --noinput --ignore input.css
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -fsS http://127.0.0.1:8000/ht/ || exit 1
# Worker: same image, command `python manage.py procrastinate worker`.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:8000 --chdir /app/src --workers ${WEB_CONCURRENCY:-2} --access-logfile - config.wsgi:application"]
