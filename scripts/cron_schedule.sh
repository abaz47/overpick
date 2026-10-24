#!/bin/bash
# Daily schedule sync + predictions (run on host via cron).
set -euo pipefail
cd /opt/overpick
exec docker compose exec -T web \
  python manage.py sync_schedule \
  >> /opt/overpick/logs/schedule.log 2>&1
