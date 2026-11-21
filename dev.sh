#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose up -d --wait typedb
uv sync --python 3.12 --frozen --extra orchestration
uv run --extra orchestration tax-benchmark verify
uv run --extra orchestration tax-benchmark seed
if [ ! -d frontend/node_modules ]; then
  npm --prefix frontend ci
fi
npm --prefix frontend run build
exec uv run --extra orchestration tax-benchmark serve
