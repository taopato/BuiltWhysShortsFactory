#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
docker compose --env-file .env.automation -f docker-compose.production.yml run --rm backup-worker python3 automation/backup_worker.py --once
git pull --ff-only
bash deploy/deploy.sh
