#!/bin/bash
# Daily 00:00 MSK batch: results → calibrate (floor) →
# schedule → locked picks for today+tomorrow calendar days.
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
