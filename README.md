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
0 20 * * * /opt/overpick/scripts/cron_daily.sh
```

`cron_daily.sh` (**20:00 MSK**): results → calibrate
(P_cal + GBM) → schedule → `build --window today`
(без force) → `build --window tomorrow --force --freeze`.
Today/Tomorrow — календарные сутки **00:00→00:00 MSK**.
После 20:00 прогнозы на завтра **замораживаются**
(`signals.frozen`) и больше не переписываются — история
выданных tip’ов не правится задним числом.

Старт сайта: `SITE_LAUNCH_AT` (по умолчанию
2026-10-24 18:00 MSK) — Today's Picks с этого времени.
History **won / picked** с `STATS_SINCE`
(2026-10-26 00:00 MSK); в списке — только
**завершённые** календарные дни MSK.
Незавершённые матчи — только Pending (без счёта в KPI).

## Прогнозы тоталов (этап 3)

База λ: `poisson_v4` (last-N + decay + att×def×liga +
Dixon–Coles). Tip: **`hybrid_v1`** =
`0.5·P_cal + 0.5·P_gbm` (LightGBM: form/rest/O2.5-rate),
порог 0.60. Продукт — **Pick Over 2.5** only.
UEFA UCL/UEL/UECL: форма клуба по всем матчам, μ — по кубку.
UI: **Picks** = календарный день 00:00→00:00 MSK.

```bash
# Today + Tomorrow (без перезаписи locked)
python manage.py build_predictions

# вечером: публикация завтра + freeze
python manage.py build_predictions --window tomorrow --force --freeze

# днём: добавить новые tip’ы, не трогая уже выданные
python manage.py refresh_signals --window today --untipped-only

# legacy: горизонт N дней / все upcoming
python manage.py build_predictions --days 3
python manage.py build_predictions --days 0
```

Калибровка порогов (длинный walk-forward):

```bash
python manage.py backtest_predictions
python manage.py calibrate_thresholds
# --apply только ужесточает глобальные thr (не ослабляет)

# прототип: Poisson vs GBM vs hybrid (не меняет tips)
python manage.py prototype_gbm
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
