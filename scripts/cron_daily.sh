#!/bin/bash
# Daily 20:00 MSK: publish Tomorrow's calendar day and freeze it.
# Never rewrites frozen tips (history / issued-tip stats stay).
set -euo pipefail
cd /opt/overpick
mkdir -p logs reports

{
  echo "=== $(date -Is) evening batch start ==="
  docker compose exec -T web \
    python manage.py sync_results
  docker compose exec -T web \
    python manage.py calibrate_thresholds
  docker compose exec -T web \
    python manage.py sync_schedule
  # Fill gaps for today if any (never --force / never unfreeze).
  docker compose exec -T web \
    python manage.py build_predictions --window today
  # Publish tomorrow once, then freeze (no later corrections).
  docker compose exec -T web \
    python manage.py build_predictions --window tomorrow --force --freeze
  echo "=== $(date -Is) evening batch done ==="
} >> /opt/overpick/logs/daily.log 2>&1
