# FitCoach Bot — техническая спецификация

Версия 1.0 · 2026-10-01
Продуктовое описание: [../PROJECT_IDEA.md](../PROJECT_IDEA.md). Краткая памятка: [../CLAUDE.md](../CLAUDE.md).

---

## 1. Обзор системы

```
 Пользователь ──► Telegram Bot API ◄──(long polling)── Бот (Python, aiogram 3)
                                                        │
                       ┌────────────────────────────────┼─────────────────────────┐
                       ▼                                ▼                         ▼
               PostgreSQL (Railway)              Claude API (Anthropic)    APScheduler (в процессе бота)
               профили, меню, логи              меню, рецепты, ответы      напоминания, сводки

 GitHub (main) ──push──► GitHub Actions (ruff + pytest) ──✓──► Railway: сборка Docker → миграции → запуск
```

- **Один сервис-воркер** на Railway + **плагин PostgreSQL** в том же проекте Railway.
- Режим получения апдейтов — **long polling** (публичный домен и HTTPS не нужны).
  Переход на webhook — опционально, позже (раздел 9.4).
- Деплой только из GitHub: push в `main` → Railway собирает и выкатывает автоматически,
  с включённой опцией **Wait for CI** (деплой только после зелёных проверок GitHub Actions).

---

## 2. Технологический стек

| Слой | Выбор | Почему |
|------|-------|--------|
| Язык | Python 3.12 | зрелая экосистема для ботов и данных |
| Telegram | aiogram 3.x | async, роутеры, FSM, middleware |
| HTTP к LLM | `anthropic` (официальный Python SDK, async-клиент) | типы, ретраи, structured outputs |
| ORM | SQLAlchemy 2.x async | типизированные модели, async-сессии |
| Драйверы БД | `asyncpg` (прод), `aiosqlite` (локально/тесты) | |
| Миграции | Alembic | выполняются pre-deploy командой на Railway |
| FSM storage | `MemoryStorage` → позже Redis (Railway plugin) | для одного пользователя достаточно памяти; потеря шага анкеты при рестарте некритична |
| Конфиг | pydantic-settings | валидация переменных окружения при старте |
| Валидация LLM | pydantic v2 | схемы меню/рецептов/ответов |
| Планировщик | APScheduler 3.x (AsyncIOScheduler) | напоминания, недельные сводки |
| Графики | matplotlib (Agg backend) | PNG-графики прогресса |
| Логи | стандартный `logging` в stdout (JSON-формат) | Railway собирает stdout |
| Качество | ruff (lint+format), mypy (опционально), pytest, pytest-asyncio | |
| Контейнер | Dockerfile (python:3.12-slim) | воспроизводимая сборка на Railway |

Зависимости фиксируются в `requirements.txt` с точными версиями (`==`).

---

## 3. Структура репозитория

```
telegram-botik1/
├── bot/
│   ├── __init__.py
│   ├── main.py                 # сборка Dispatcher, роутеры, middleware, scheduler, start_polling
│   ├── config.py               # Settings (pydantic-settings)
│   ├── logging.py              # настройка логов
│   ├── handlers/
│   │   ├── start.py            # /start, дисклеймер, запуск анкеты
│   │   ├── profile.py          # анкета (FSM), /profile
│   │   ├── nutrition.py        # /norm, /menu, /recipe, /shopping, замена блюда
│   │   ├── ask.py              # /ask — свободные вопросы
│   │   ├── workouts.py         # этап 2
│   │   ├── progress.py         # этап 3
│   │   └── errors.py           # глобальный обработчик ошибок
│   ├── keyboards/              # фабрики inline-клавиатур, CallbackData-классы
│   ├── states/                 # StatesGroup для анкеты и др.
│   ├── middlewares/
│   │   ├── db.py               # открывает AsyncSession на апдейт
│   │   ├── access.py           # белый список пользователей (ALLOWED_USER_IDS)
│   │   └── throttling.py       # антиспам / лимиты на LLM-команды
│   ├── services/               # чистая бизнес-логика, без aiogram
│   │   ├── kbju.py             # BMR, TDEE, дефицит, макросы
│   │   ├── nutrition_calc.py   # КБЖУ ингредиента/блюда/дня, масштабирование порций
│   │   ├── meal_plan.py        # оркестрация генерации меню (LLM + валидация + пересчёт)
│   │   ├── shopping.py         # агрегация списка покупок
│   │   ├── workout_plan.py     # этап 2
│   │   └── progress.py         # этап 3
│   ├── llm/
│   │   ├── client.py           # AsyncAnthropic, общие параметры, обработка ошибок/refusal
│   │   ├── prompts.py          # системные промпты (стабильные — для кэширования)
│   │   └── schemas.py          # pydantic-схемы ответов LLM
│   ├── db/
│   │   ├── base.py             # engine, async_sessionmaker, DeclarativeBase
│   │   ├── models.py           # ORM-модели
│   │   └── repo/               # репозитории: users.py, products.py, meal_plans.py, ...
│   ├── scheduler.py            # регистрация задач APScheduler (этап 3)
│   └── data/
│       ├── products.csv        # справочник продуктов: КБЖУ на 100 г
│       └── exercises.yaml      # справочник упражнений (этап 2)
├── migrations/                 # Alembic (env.py async)
├── scripts/
│   └── seed_products.py        # загрузка справочников в БД (идемпотентно)
├── tests/
│   ├── unit/                   # kbju, nutrition_calc, shopping, валидация схем
│   └── integration/            # хендлеры с моками Bot/LLM, БД на SQLite in-memory
├── docs/
│   └── TECH_SPEC.md
├── .github/workflows/ci.yml
├── Dockerfile
├── .dockerignore
├── railway.toml
├── alembic.ini
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml              # настройки ruff, pytest
├── .env.example
├── .gitignore
├── CLAUDE.md
└── PROJECT_IDEA.md
```

**Правило слоёв:** `handlers` → `services` → `db/repo` и `llm`. Сервисы не импортируют aiogram;
хендлеры не пишут SQL и не вызывают LLM напрямую.

---

## 4. Конфигурация и секреты

Все секреты — только в переменных окружения. Локально — файл `.env` (в `.gitignore`),
на Railway — вкладка **Variables** сервиса.

| Переменная | Обязательна | Пример / описание |
|------------|-------------|-------------------|
| `BOT_TOKEN` | да | токен от @BotFather |
| `ANTHROPIC_API_KEY` | да | ключ Claude API |
| `DATABASE_URL` | да | на Railway: `${{Postgres.DATABASE_URL}}` (reference variable); локально `sqlite+aiosqlite:///./dev.db` |
| `ALLOWED_USER_IDS` | да | список Telegram ID через запятую — доступ только владельцу |
| `LLM_MODEL` | нет | по умолчанию `claude-opus-5-5` |
| `LLM_EFFORT` | нет | по умолчанию `medium` |
| `DEFAULT_TZ` | нет | `Europe/Moscow` |
| `LOG_LEVEL` | нет | `INFO` |
| `ASK_DAILY_LIMIT` | нет | лимит `/ask` в сутки, по умолчанию 30 |

`config.py` нормализует `DATABASE_URL`: Railway отдаёт `postgresql://…`, для SQLAlchemy async
схема заменяется на `postgresql+asyncpg://…`. Бот не стартует, если обязательные переменные пусты.

---

## 5. Модель данных

Типы указаны для PostgreSQL. Все таблицы имеют `id` (PK), `created_at`, `updated_at` где уместно.

### Этап 1
| Таблица | Поля |
|---------|------|
| `users` | `tg_id` (BIGINT, unique), `first_name`, `sex` (enum m/f), `birth_year`, `height_cm`, `weight_kg` (NUMERIC 5,1), `activity` (enum: sedentary/light/moderate/high), `goal` (enum: lose/maintain), `meals_per_day` (3–5), `excluded_products` (JSONB, список), `restrictions_text`, `tz`, `onboarded` (bool) |
| `nutrition_targets` | `user_id` FK, `bmr`, `tdee`, `kcal`, `protein_g`, `fat_g`, `carbs_g`, `deficit_pct`, `is_active` |
| `products` | `name` (unique), `aliases` (JSONB), `category` (enum: мясо, рыба, крупы, овощи…), `kcal_100`, `protein_100`, `fat_100`, `carbs_100`, `unit_weight_g` (вес 1 шт., nullable) |
| `recipes` | `title`, `meal_type` (breakfast/lunch/dinner/snack), `steps` (JSONB, список строк), `cook_minutes`, `servings`, `source` (llm/manual), `rating` (nullable), `is_blocked` |
| `recipe_ingredients` | `recipe_id` FK, `product_id` FK, `grams` |
| `meal_plans` | `user_id` FK, `week_start` (date), `target_id` FK, `status` (draft/active/archived) |
| `meal_plan_items` | `meal_plan_id` FK, `day` (0–6), `meal_type`, `recipe_id` FK, `portion_factor` (NUMERIC), кэш `kcal/protein/fat/carbs` |
| `llm_requests` | `user_id`, `kind` (menu/recipe/ask), `model`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `latency_ms`, `status` — учёт стоимости |

### Этап 2
`exercises` (название, мышечные группы, паттерн движения, оборудование: gym/home/both, уровень,
техника, частые ошибки, противопоказания, `alternative_ids`),
`workout_programs` (user, тип: gym/home/mixed, уровень, неделя цикла, статус),
`workout_templates` (программа, день A/B/C, порядок упражнений, подходы, повторы, RPE, отдых).

### Этап 3
`body_logs` (дата, вес, талия, бёдра, грудь, заметка),
`workout_logs` (дата, шаблон, выполнено, самочувствие 1–5),
`set_logs` (workout_log, упражнение, подход, вес, повторы, RPE),
`reminders` (тип, время, дни недели, включено).

---

## 6. Ключевые алгоритмы (детерминированный код)

### 6.1. Норма КБЖУ — `services/kbju.py`
1. `BMR` по Миффлину-Сан Жеору (м: `+5`, ж: `−161`).
2. `TDEE = BMR × k`, k ∈ {1.2, 1.375, 1.55, 1.725}.
3. Цель «снижение»: `kcal = TDEE × (1 − 0.17)`, при этом `TDEE − kcal ≤ 500` и `kcal ≥ BMR`
   (никогда не ниже базового обмена).
4. Белок `1.8 г × вес`, жиры `0.9 г × вес` (не менее 20% ккал), углеводы — остаток.
   Ккал на грамм: Б 4, Ж 9, У 4.
5. Округление: ккал до 10, макросы до 1 г.
6. Пересчёт при изменении веса ≥ 2 кг или по команде.

### 6.2. КБЖУ блюда и дня — `services/nutrition_calc.py`
- `КБЖУ ингредиента = значение_на_100 × граммы / 100`.
- Блюдо = сумма ингредиентов × `portion_factor`.
- Подбор порций под цель дня: решаем масштабирование `portion_factor` для каждого приёма пищи
  (ограничение 0.6–1.5), чтобы попасть в `kcal` ±5% и белок ≥ 90% нормы.
  Простая итеративная подгонка, без внешних солверов.
- Если попасть не удалось — блюдо с наибольшим отклонением перегенерируется (не более 2 попыток).

### 6.3. Список покупок — `services/shopping.py`
Сумма граммов по `product_id` за неделю с учётом `portion_factor` → округление вверх до
разумных единиц (шт. по `unit_weight_g`, иначе 50 г) → группировка по `category`.

Все функции этого раздела — чистые, покрываются unit-тестами с эталонными значениями.

---

## 7. Интеграция с Claude API

### 7.1. Принципы
- **LLM придумывает, код считает.** Модель возвращает блюда, ингредиенты (названия из
  переданного ей списка продуктов) и граммовки. Числа КБЖУ от модели игнорируются.
- **Структурированный вывод:** `client.messages.parse(...)` с pydantic-моделью
  (`output_config.format`) — ответ гарантированно соответствует схеме.
- **Модель:** `claude-opus-5-5`, `output_config.effort`: `medium` для меню и рецептов,
  `low` для коротких ответов `/ask`. Параметр `thinking` не передаём (на Opus 5.5 он всегда
  адаптивный; `disabled` и `budget_tokens` дают ошибку 400).
- **Отказы:** всегда проверяем `stop_reason` до чтения контента. Включаем серверный fallback
  (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`); при `refusal` —
  вежливое сообщение пользователю и запись в лог.
- **Кэширование промптов:** системный промпт и справочник продуктов — стабильный префикс
  с `cache_control`; переменные данные (профиль, дата, ограничения) — в конце запроса.
  Проверка: `usage.cache_read_input_tokens > 0` на повторных запросах.
- **Таймауты и ретраи:** SDK ретраит 429/5xx (`max_retries=2`); общий таймаут запроса 120 с;
  в чате пользователь видит «Составляю меню…» (chat action `typing` + сообщение-заглушка,
  которое потом редактируется).
- **Ошибки:** цепочка `RateLimitError` → `APIStatusError` → `APIConnectionError`;
  пользователю — понятный текст, без трассировок.

### 7.2. Сценарии
| Сценарий | Вход | Выход (pydantic-схема) |
|----------|------|------------------------|
| Меню на день | цель КБЖУ, кол-во приёмов, исключения, список продуктов, уже использованные блюда недели | `DayMenu{meals: [Meal{meal_type, title, cook_minutes, ingredients: [{product, grams}], steps: [str]}]}` |
| Замена блюда | то же + КБЖУ слота | `Meal` |
| Свободный вопрос | вопрос + краткий профиль | `Answer{text, needs_doctor: bool}` |

Неделя генерируется как 7 запросов «меню на день» (параллельно, `asyncio.gather` с ограничением
конкурентности 3), с передачей уже выбранных блюд для разнообразия.

### 7.3. Валидация ответа
1. Каждый `product` сопоставляется со справочником (точное совпадение → `aliases` → нормализация
   регистра/ё). Неизвестный продукт → перегенерация блюда.
2. Санитарные границы граммовок: масло/жиры ≤ 30 г, соль/специи ≤ 10 г, порция блюда
   150–700 г, число шагов 2–12.
3. Пересчёт КБЖУ кодом и подгонка порций (6.2).
4. Сохранение рецепта в `recipes` — со временем копится библиотека проверенных блюд,
   которые можно переиспользовать без LLM.

### 7.4. Тренировки (этап 2)
LLM **не генерирует** упражнения. Программа собирается кодом из шаблонов (full body A/B/C,
3×/нед) и справочника `exercises.yaml` с учётом места (зал/дом), уровня и противопоказаний.
LLM допустимо использовать только для текстовых пояснений и мотивации.

---

## 8. Пользовательские сценарии (UX-контракт)

- Все действия — через inline-кнопки; команды дублируют главное меню.
- Длинные операции: «⏳ Составляю меню на неделю…», затем результат по дням (карусель кнопками
  «◀ Пн … Вс ▶»), чтобы не упереться в лимит 4096 символов сообщения.
- Рецепт: отдельное сообщение с ингредиентами, шагами и КБЖУ порции.
- Ошибка/недоступность LLM: «Сервис временно недоступен, попробуйте через минуту» + кнопка «Повторить».
- Дисклеймер при первом запуске; в `/ask` при `needs_doctor = true` — рекомендация врача.
- Доступ: middleware отклоняет пользователей вне `ALLOWED_USER_IDS`.

---

## 9. Инфраструктура и деплой (Railway + GitHub)

### 9.1. Проект Railway
- Проект `fitcoach-bot`, окружение `production`.
- Сервис **bot** — источник: GitHub-репозиторий `Kris30-max/telegram-botik1`, ветка `main`,
  автодеплой включён, **Wait for CI** включён.
- Сервис **Postgres** — плагин Railway; в переменные бота пробрасывается
  `DATABASE_URL=${{Postgres.DATABASE_URL}}`.
- **Replicas = 1.** Две копии бота в режиме polling конфликтуют
  (`TelegramConflictError: terminated by other getUpdates request`).

### 9.2. `railway.toml` (config as code)
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
preDeployCommand = ["alembic upgrade head"]
startCommand = "python -m bot.main"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```
Во время выкатки старый и новый контейнер могут кратко работать одновременно — для polling
это даёт несколько секунд предупреждений о конфликте; бот должен корректно завершаться по SIGTERM
(`dp.stop_polling()`, закрытие сессий БД и HTTP), чтобы окно было минимальным.

### 9.3. Dockerfile (схема)
`python:3.12-slim` → установка `requirements.txt` (слой кэшируется) → копирование кода →
непривилегированный пользователь → `CMD ["python", "-m", "bot.main"]`.
`PYTHONUNBUFFERED=1`, чтобы логи сразу попадали в Railway.

### 9.4. Webhook (опционально, позже)
Если понадобится: включить публичный домен сервиса, поднять `aiohttp`-сервер на `$PORT`,
`setWebhook` на `https://$RAILWAY_PUBLIC_DOMAIN/tg/<secret>` с `secret_token`, эндпоинт
`/health` для healthcheck. До этого — polling.

### 9.5. CI — `.github/workflows/ci.yml`
На `push` и `pull_request`: установка Python 3.12 → `pip install -r requirements-dev.txt` →
`ruff check .` → `ruff format --check .` → `pytest -q`. Тесты не требуют сети и секретов
(LLM и Telegram замоканы, БД — SQLite in-memory).

### 9.6. Ветки и релизы
- `main` — всегда деплоится в production.
- Фичи — в ветках `feat/<название>`, слияние через Pull Request после зелёного CI.
- Коммиты в стиле Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).
- Опционально: окружение Railway `staging` из ветки `dev` с отдельным тестовым ботом.

### 9.7. Доступ к GitHub
Секреты (токены GitHub, BotFather, Anthropic) **никогда** не коммитятся и не пишутся в
конфиги репозитория. Авторизация git на рабочей машине — через Git Credential Manager или
`gh auth login`.

---

## 10. Надёжность, наблюдаемость, данные

- **Логи:** JSON в stdout; на каждый апдейт — `update_id`, `user_id`, хендлер, длительность;
  на каждый LLM-запрос — модель, токены, cache read, задержка (без текстов личных данных).
- **Глобальный error handler** aiogram: логирует исключение, пользователю — нейтральное сообщение.
- **Стоимость LLM:** таблица `llm_requests` + команда администратора `/stats` (токены за неделю).
  Лимит `/ask` в сутки; меню генерируется раз в неделю и кэшируется в БД.
- **Бэкапы:** включить бэкапы Postgres в Railway; дополнительно — ручной `pg_dump` перед
  крупными миграциями.
- **Персональные данные:** храним минимум (без фото на этапах 1–2); команда `/delete_me`
  удаляет все данные пользователя.
- **Graceful shutdown** по SIGTERM (Railway шлёт его при каждом деплое).

---

## 11. Тестирование

| Уровень | Что | Инструменты |
|---------|-----|-------------|
| Unit | `kbju`, `nutrition_calc`, `shopping`, подгонка порций, валидация схем LLM, санитарные границы | pytest, эталонные значения |
| Integration | хендлеры анкеты и меню: фейковый апдейт → ответ бота; LLM — фикстуры с валидными/битыми JSON | pytest-asyncio, моки `Bot` и `AsyncAnthropic` |
| Ручной smoke | после деплоя: `/start`, анкета, `/menu`, рецепт, список покупок | тестовый аккаунт |

Эталон для КБЖУ: м, 30 лет, 180 см, 85 кг, активность 1.55 →
BMR = 10·85 + 6.25·180 − 5·30 + 5 = 1830; TDEE = 2836.5; дефицит 17% → 2354 → ограничение
«не больше 500 ккал» не срабатывает (482) → **2350 ккал**.

Критерий «задача готова»: `ruff check .` и `pytest` зелёные локально и в CI.

---

## 12. План разработки (технические шаги)

### Этап 0 — каркас и инфраструктура
1. Установить на машину Git и Python 3.12; клонировать репозиторий.
2. Каркас: `pyproject.toml`, `requirements*.txt`, `.gitignore`, `.env.example`, `bot/config.py`,
   `bot/main.py` с `/start` → «Привет».
3. Dockerfile, `railway.toml`, CI workflow.
4. Railway: проект, Postgres, сервис из GitHub, переменные, Wait for CI.
5. Первый деплой: бот отвечает на `/start` из Railway. ✔ — этап закрыт.

### Этап 1 — питание (MVP)
1. БД: модели этапа 1, первая миграция Alembic, seed справочника продуктов (200–300 позиций).
2. Анкета (FSM) + `/profile`.
3. `services/kbju.py` + тесты → `/norm`.
4. `llm/` клиент, схемы, промпты; `services/meal_plan.py` с валидацией и подгонкой порций + тесты.
5. `/menu` (неделя, навигация по дням), рецепт, замена блюда.
6. `/shopping`, `/ask` с лимитом.
7. Логи стоимости, `/stats`, `/delete_me`.

### Этап 2 — тренировки
Справочник упражнений → шаблоны программ → генератор программы → `/workout`, `/program`,
ведение тренировки, прогрессия и разгрузка → проверка по чек-листу из PROJECT_IDEA.md.

### Этап 3 — прогресс
`/weight`, `/measure`, `/done` → графики → APScheduler-напоминания с учётом часового пояса →
недельная сводка → автокорректировка калорий и нагрузок.

---

## 13. Решения и их обоснование (ADR, кратко)

| # | Решение | Альтернатива | Почему так |
|---|---------|--------------|------------|
| 1 | Long polling | Webhook | не нужен домен/HTTPS, проще на Railway, нагрузка мизерная |
| 2 | PostgreSQL на Railway сразу в проде | SQLite в volume | SQLite на volume теряет простоту бэкапов и миграций; Postgres — плагин в один клик |
| 3 | КБЖУ считает код | КБЖУ от LLM | LLM ошибается в арифметике и в табличных значениях |
| 4 | Тренировки из шаблонов | Генерация LLM | безопасность и предсказуемость, «как у опытного тренера» |
| 5 | Dockerfile | Автосборка Railway (Railpack) | одинаковое окружение локально, в CI и в проде |
| 6 | MemoryStorage для FSM | Redis | один пользователь; Redis добавим при мультипользовательском режиме |
| 7 | Доступ по белому списку | Открытый бот | контроль расходов на LLM и приватность |
