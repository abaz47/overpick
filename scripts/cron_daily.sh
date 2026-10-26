#!/bin/bash
# Daily 20:00 MSK: lock Tomorrow's calendar day without
# touching Today's already locked tips (00:00→00:00 MSK).
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
  # Fill gaps for today if any (never --force).
  docker compose exec -T web \
    python manage.py build_predictions --window today
  # Rebuild tomorrow only.
  docker compose exec -T web \
    python manage.py build_predictions --window tomorrow --force
  docker compose exec -T web \
    python manage.py refresh_signals --window tomorrow
  echo "=== $(date -Is) evening batch done ==="
} >> /opt/overpick/logs/daily.log 2>&1
