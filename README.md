# OverPick

Аналитика футбольных тоталов (О1.5 / О2.5 / О3.5)
по форме команд дома и в гостях.

Стек этапа 0: **Python 3.14**, **Django 6.1**,
templates + Bootstrap 5, ruff / djlint / pre-commit.

## Быстрый старт

```bash
cd /home/abaz/dev/tips/overpick
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# отредактируйте .env (SECRET_KEY и т.д.)

pre-commit install
python manage.py migrate
python manage.py runserver
```

Откройте http://127.0.0.1:8000/
Health: http://127.0.0.1:8000/health/

## Синхронизация матчей (этап 2)

В `.env` укажите реальный `API_FOOTBALL_KEY`, затем:

```bash
# разовая заливка истории
python manage.py seed_leagues --from-season 2022 --to-season 2026
python manage.py sync_fixtures --force --max-requests 200

# ежедневно: календарь текущих сезонов + прогнозы (~40 req)
python manage.py sync_schedule

# каждый час: счета сегодня/вчера MSK (~2 req) → History
python manage.py sync_results
```

На VPS cron (см. `scripts/cron_*.sh`):

```cron
5 * * * * /opt/overpick/scripts/cron_results.sh
30 7 * * * /opt/overpick/scripts/cron_daily.sh
```

`cron_daily.sh` (07:30 MSK): results → calibrate
(league overrides только **строже** глобальных) →
schedule + `build_predictions` на окно суток →
`refresh_signals`.

Старт сайта: `SITE_LAUNCH_AT` (по умолчанию
2026-10-24 18:00 MSK) — Today's Picks с этого времени.
History **won / picked** с `STATS_SINCE`
(2026-10-25 00:00 MSK), периоды Yesterday/2/3/Week/Month.
Ежедневный lock Today+Tomorrow: cron 07:30 MSK.
Незавершённые матчи — только Pending (без счёта в KPI).

## Прогнозы тоталов (этап 3)

Модель `poisson_v4`: last-N с decay + attack×defence×liga
(без double-count opp-adjust) + caps на индексы/λ +
Dixon–Coles. Продукт: независимые **Pick Over 2.5** и
**Pick BTTS** (отдельные KPI; один ряд в таблице, если оба).
O1.5/O3.5 только как контекст на карточке матча.
UI: **Picks** = locked batch 07:30→+24h MSK.

```bash
# текущий суточный batch (07:30 MSK, +24h)
python manage.py build_predictions

# обновить только бейджи Pick на уже сохранённых
python manage.py refresh_signals

# legacy: горизонт N дней / все upcoming
python manage.py build_predictions --days 3
python manage.py build_predictions --days 0

# перезаписать locked-прогнозы batch
python manage.py build_predictions --force
```

Калибровка порогов (длинный walk-forward):

```bash
python manage.py backtest_predictions
python manage.py calibrate_thresholds
# --apply только ужесточает глобальные thr (не ослабляет)
```

Проверка без API:

```bash
pytest
```

## Деплой (aeza-spb1)

Прод: **https://overpick.n0bl0ck.space**
(`127.0.0.1:8040` за nginx).

```bash
# на сервере: /opt/overpick + .env (секреты не в git)
docker compose up -d --build
docker compose exec web \
  python manage.py sync_fixtures --max-requests 200
docker compose exec web \
  python manage.py build_predictions
docker compose exec web \
  python manage.py backtest_predictions
```

## Линтеры

PEP 8, длина строки **не более 79**.

```bash
ruff check .
ruff format .
djlint templates/ --check
# или автоформат шаблонов:
djlint templates/ --reformat
```

Перед коммитом сработает `pre-commit`
(ruff, djlint, detect-private-key).

## Секреты

- Реальные ключи только в **`.env`** (в gitignore).
- В репозиторий — только **`.env.example`**.
- Не коммитьте `*.pem`, SSH-ключи, дампы БД.

## Структура

```text
config/              # Django project (settings, urls)
apps/core/           # /health/
apps/dashboard/      # Upcoming / History / Detail / Leagues
apps/leagues/        # League, Team
apps/matches/        # Fixture
apps/predictions/    # Prediction + poisson_v3
templates/           # Django templates + Bootstrap
```

UI: `/` Today's Picks, `/tomorrow/` Tomorrow's Picks,
`/history/` по дням, `/matches/<id>/`.

## Этапы

- [x] 0 — каркас, линтеры, health/home
- [x] 1 — модели League / Team / Fixture / Prediction
- [x] 2 — sync API-Football (+ история сезонов)
- [x] 3 — Poisson-прогнозы (`build_predictions`)
- [x] 4 — Upcoming / Detail / History / Leagues
- [x] 5 — Docker
- [x] 6 — деплой aeza-spb1 + overpick.n0bl0ck.space
