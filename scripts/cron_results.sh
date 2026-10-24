#!/bin/bash
# Hourly results sync (run on host via cron).
set -euo pipefail
cd /opt/overpick
exec docker compose exec -T web \
  python manage.py sync_results \
  >> /opt/overpick/logs/results.log 2>&1
