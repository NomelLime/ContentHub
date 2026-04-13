# Migration: Agent Events Registry (`contenthub.db`)

Добавляет/выравнивает таблицу `agent_events` для дашбордов hook/risk/experiment:

- `source_project`
- `agent_name`
- `event_type`
- `severity`
- `creative_id`
- `hook_type`
- `experiment_id`
- `agent_run_id`
- `payload_json`
- `created_at`

## 1) Бэкап БД

```bash
cp /path/to/ContentHub/backend/contenthub.db "/var/backups/contenthub.db.$(date +%Y%m%d_%H%M%S)"
```

## 2) Применение миграции (безопасно, можно повторять)

```bash
cd /path/to/ContentHub
python scripts/migrate_contenthub_db.py --db /path/to/ContentHub/backend/contenthub.db
```

## 3) Проверка структуры таблицы

```bash
sqlite3 /path/to/ContentHub/backend/contenthub.db "PRAGMA table_info(agent_events);"
```

## 4) Проверка индексов

```bash
sqlite3 /path/to/ContentHub/backend/contenthub.db "PRAGMA index_list(agent_events);"
```

Ожидаются индексы:

- `idx_agent_events_created`
- `idx_agent_events_hook`
- `idx_agent_events_experiment`
