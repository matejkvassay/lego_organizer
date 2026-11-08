FROM node:22-slim AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY --from=frontend /fe/dist /app/frontend/dist
ENV PATH="/app/backend/.venv/bin:$PATH" \
    DATABASE_URL=sqlite:////data/lego.db \
    FRONTEND_DIST=/app/frontend/dist
RUN useradd --system --uid 10001 --no-create-home app && mkdir -p /data && chown app /data
USER app   # never run the web process as root
VOLUME /data
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
