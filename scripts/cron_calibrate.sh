#!/bin/bash
# Prefer cron_daily.sh at 00:00 MSK. Kept for manual runs.
set -euo pipefail
cd /opt/overpick
mkdir -p logs reports
exec docker compose exec -T web \
  python manage.py calibrate_thresholds \
  >> /opt/overpick/logs/calibrate.log 2>&1
