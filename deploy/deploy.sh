#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
test -f .env.automation || { echo "Missing .env.automation"; exit 2; }
mkdir -p storage/backups storage/archives storage/thumbnails automation/pilots
chmod 600 .env.automation
chmod 600 config.toml
python3 automation/preflight.py --env-file .env.automation --online
docker compose --env-file .env.automation -f docker-compose.production.yml build
docker compose --env-file .env.automation -f docker-compose.production.yml up -d
echo "Waiting for Control Center health..."
for _ in $(seq 1 60); do
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' builtwhys-control-center-1 2>/dev/null || true)"
  [ "$status" = "healthy" ] && break
  sleep 5
done
docker compose --env-file .env.automation -f docker-compose.production.yml ps
curl -fsS http://127.0.0.1/healthz >/dev/null || true
echo "Deployment finished. Live publishing remains controlled by both PUBLISH_ENABLED and the Control Center setting."
