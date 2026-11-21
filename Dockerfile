FROM node:24-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
COPY data/ ./data/
COPY typedb/ ./typedb/
COPY config/ ./config/
RUN uv sync --frozen --no-dev --extra orchestration
COPY --from=frontend /app/frontend/dist ./frontend/dist
EXPOSE 8000
CMD ["sh", "-c", "uv run --frozen --no-dev --extra orchestration tax-benchmark seed && exec uv run --frozen --no-dev --extra orchestration tax-benchmark serve --host 0.0.0.0 --port 8000"]
