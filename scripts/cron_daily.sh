#!/bin/bash
# Daily 20:00 MSK batch: results → calibrate (floor) →
# schedule → locked picks for the next 48h (Today+Tomorrow).
set -euo pipefail
cd /opt/overpick
mkdir -p logs reports

{
  echo "=== $(date -Is) daily batch start ==="
  docker compose exec -T web \
    python manage.py sync_results
  docker compose exec -T web \
    python manage.py calibrate_thresholds
  docker compose exec -T web \
    python manage.py sync_schedule
  docker compose exec -T web \
    python manage.py build_predictions --force
  docker compose exec -T web \
    python manage.py refresh_signals
  echo "=== $(date -Is) daily batch done ==="
} >> /opt/overpick/logs/daily.log 2>&1
