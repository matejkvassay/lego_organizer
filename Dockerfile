# Base images are pinned to exact versions; bump them deliberately (and re-run the tests).
FROM node:22.23.4-bookworm-slim AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12.16-slim-bookworm AS litestream
COPY deploy/fetch_litestream.py /fetch_litestream.py
RUN python /fetch_litestream.py && chmod 0755 /litestream

FROM python:3.12.16-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
COPY --from=litestream /litestream /usr/local/bin/litestream
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY --from=frontend /fe/dist /app/frontend/dist
COPY deploy/litestream.yml /etc/litestream.yml
COPY deploy/entrypoint.sh /app/entrypoint.sh
ENV PATH="/app/backend/.venv/bin:$PATH" \
    DATABASE_URL=sqlite:////data/lego.db \
    FRONTEND_DIST=/app/frontend/dist
RUN chmod 0755 /app/entrypoint.sh \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app && mkdir -p /data && chown app /data
# Never run the web process as root.
USER app
VOLUME /data
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
