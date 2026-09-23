# Контракт: данные и API

Фиксируется в первые 30 минут. Дальше не меняется без согласия всей команды.
Это то, что позволяет троим работать параллельно и состыковаться без переписывания.

---

## 1. Карточка задачи (`Task`)

Состав полей задан кейсом, менять нельзя.

```json
{
  "id": "t_001",
  "title": "Название",
  "industry": "retail",
  "context": "Что происходит сейчас",
  "need": "Что необходимо изменить",
  "users": "Для кого создаётся решение",
  "data_materials": "Доступные данные, примеры, источники",
  "constraints": "Сроки, технологии, доступы, границы",
  "expected_result": "Конкретный результат работы команды",
  "success_criteria": "Измеримые признаки принятия решения",
  "contact": "Имя и способ связи",
  "interaction_format": "Формат консультаций и обратной связи",
  "status": "draft",
  "rating": {
    "score": 0,
    "level": "draft",
    "breakdown": [],
    "missing": [],
    "tips": []
  },
  "created_at": "2026-09-23T10:00:00"
}
```

`status`: `"draft"` (черновик, не в каталоге) или `"published"` (в каталоге).
Пустое поле = пустая строка `""`, а не `null`.

## 2. Рейтинг (`Rating`)

```json
{
  "score": 65,
  "level": "working",
  "breakdown": [
    {"key": "context_need", "label": "Контекст и потребность", "earned": 20, "max": 20, "filled": true},
    {"key": "data_materials", "label": "Данные и материалы", "earned": 0, "max": 20, "filled": false}
  ],
  "missing": ["data_materials", "success_criteria"],
  "tips": ["Добавьте, какие данные вы готовы предоставить — это +20 баллов"]
}
```

**Показатели и веса** (из кейса, сумма 100):

| key | Показатель | Вес | Поля карточки |
| --- | --- | --- | --- |
| `context_need` | Контекст и потребность | 20 | `context`, `need` |
| `data_materials` | Данные и материалы | 20 | `data_materials` |
| `expected_result` | Ожидаемый результат | 15 | `expected_result` |
| `success_criteria` | Критерии успеха | 15 | `success_criteria` |
| `constraints` | Ограничения | 10 | `constraints` |
| `users` | Пользователи | 10 | `users` |
| `business_link` | Связь с бизнесом | 10 | `contact`, `interaction_format` |

**Уровни готовности:**

| level | Диапазон | Подпись в интерфейсе |
| --- | --- | --- |
| `draft` | 0–39 | Черновик — требует уточнения |
| `working` | 40–69 | Рабочая — можно откликаться |
| `ready` | 70–89 | Готовая |
| `priority` | 90–100 | Приоритетная |

Показатель из двух полей засчитывается полностью, только если заполнены оба;
если заполнено одно — половина веса. Баллы начисляются только за заполненные поля.

## 3. Профиль команды (`Team`)

```json
{
  "id": "team_01",
  "name": "Название",
  "interests": ["аналитика", "образование"],
  "skills": ["Python", "SQL"],
  "technologies": ["FastAPI", "Pandas"]
}
```

## 4. Предложение (`Proposal`)

```json
{
  "id": "p_001",
  "task_id": "t_001",
  "team_id": "team_01",
  "idea": "Идея решения",
  "plan": "План работы",
  "deadline": "2 недели",
  "link": "https://...",
  "status": "new",
  "created_at": "2026-09-23T11:00:00"
}
```

`status`: `"new"` | `"accepted"` | `"rejected"`. Меняется только вручную бизнесом.

---

## 5. API

Все ответы: HTTP 200, различие через поле `ok`.

```json
{"ok": true, "data": {...}}
{"ok": false, "error": {"code": "invalid_input", "message": "Понятный текст"}}
```

Коды ошибок: `invalid_input`, `not_found`, `ai_error`, `internal_error`.

### Конструктор задачи

| Метод | Путь | Вход | Выход |
| --- | --- | --- | --- |
| `POST` | `/api/analyze` | `{"draft": "текст", "industry": "retail"}` | `{"questions": [...], "missing": [...], "source": "ai"}` |
| `POST` | `/api/build-card` | `{"draft": "...", "answers": [{"key": "...", "question": "...", "answer": "..."}]}` | `{"card": Task, "source": "ai"}` |

`questions` — минимум 3 объекта `{"key": "data_materials", "question": "..."}`.
`key` совпадает с ключом показателя рейтинга — это связывает вопросы с баллами.

`source`: `"ai"` или `"fallback"`, если модель недоступна.

### Рейтинг

| Метод | Путь | Вход | Выход |
| --- | --- | --- | --- |
| `POST` | `/api/rating` | `{"card": Task}` | `{"rating": Rating}` |

Чистый расчёт, без сохранения. Используется для живого пересчёта при редактировании.

### Задачи и каталог

| Метод | Путь | Вход | Выход |
| --- | --- | --- | --- |
| `POST` | `/api/tasks` | `{"card": Task}` | `{"task": Task}` — сохраняет, считает рейтинг, `status: "published"` |
| `GET` | `/api/tasks` | query: `industry`, `level`, `sort=rating\|date` | `{"tasks": [Task]}` — по умолчанию сортировка по `rating.score` убыв. |
| `GET` | `/api/tasks/{id}` | — | `{"task": Task}` |
| `PUT` | `/api/tasks/{id}` | `{"card": Task}` | `{"task": Task}` — пересчитывает рейтинг |

### Отклики и решение бизнеса

| Метод | Путь | Вход | Выход |
| --- | --- | --- | --- |
| `GET` | `/api/teams` | — | `{"teams": [Team]}` |
| `POST` | `/api/tasks/{id}/proposals` | `{"team_id", "idea", "plan", "deadline", "link"}` | `{"proposal": Proposal}` |
| `GET` | `/api/tasks/{id}/proposals` | — | `{"proposals": [Proposal]}` |
| `POST` | `/api/proposals/{id}/decision` | `{"decision": "accepted"\|"rejected"}` | `{"proposal": Proposal}` |

Отклик принимается независимо от рейтинга задачи. Решение — только явным вызовом
с фронтенда по нажатию кнопки.

### Рекомендации

| Метод | Путь | Вход | Выход |
| --- | --- | --- | --- |
| `GET` | `/api/recommendations` | query: `team_id` | `{"tasks": [Task], "reason": {...}}` |

Рекомендации не сужают каталог: полный список всегда доступен через `/api/tasks`.

### Фактический прогресс выбранной команды

Кейс требует начислять выбранной команде баллы за фактический прогресс после
подтверждения этапа, но не задаёт число баллов и формат этапа. MVP хранит каждый
отчёт отдельно: `proposal_id`, `task_id`, `team_id`, `result`, `evidence_link`,
`status` (`submitted` | `confirmed` | `rejected`), `points` и временные метки.
Отчёт доступен только по принятому бизнесом предложению. Команда отправляет
описание фактического результата и ссылку на доказательство; бизнес вручную
подтверждает или отклоняет отчёт. Очки появляются только при подтверждении,
решение можно вынести только один раз. Для демо MVP выбрано 10 баллов за один
подтверждённый этап — это открытое проектное допущение, а не число из PDF.

| Метод | Путь | Назначение |
| --- | --- | --- |
| `POST` | `/api/proposals/{id}/progress` | Команда принятого предложения отправляет `result` и `evidence_link` |
| `GET` | `/api/proposals/{id}/progress` | Получить отчёты этапов для предложения |
| `POST` | `/api/progress/{id}/decision` | Бизнес отправляет `{"decision":"confirmed"}` или `rejected` |
| `GET` | `/api/progress` | Табло команд по очкам за подтверждённый прогресс |

### Служебное

| Метод | Путь | Выход |
| --- | --- | --- |
| `GET` | `/api/health` | `{"status": "ok"}` |
| `GET` | `/` | Интерфейс |

---

## 6. Публичные функции модулей

```python
# core/rating.py  — участник 3, чистые функции
def calculate_rating(card: dict) -> dict          # -> Rating
def get_level(score: int) -> str                  # -> "draft"|"working"|"ready"|"priority"
def missing_fields(card: dict) -> list[str]

# core/ai.py      — участник 1
def analyze_draft(draft: str, industry: str) -> dict   # -> {"questions": [...], "missing": [...], "source": ...}
def build_card(draft: str, answers: list[dict]) -> dict # -> {"card": {...}, "source": ...}

# core/store.py   — участник 3
def load_tasks() -> list[dict]
def get_task(task_id: str) -> dict | None
def save_task(task: dict) -> dict
def load_teams() -> list[dict]
def load_proposals(task_id: str | None = None) -> list[dict]
def save_proposal(proposal: dict) -> dict
def update_proposal_status(proposal_id: str, status: str) -> dict | None
```

Ни одна из них не выбрасывает исключение наружу при некорректном входе —
возвращает пустой результат или `None`.

---

## 7. Заглушки первых 20 минут

Чтобы никто никого не ждал, каждый сразу коммитит свою функцию-заглушку,
возвращающую корректную структуру:

```python
# core/ai.py
def analyze_draft(draft, industry=""):
    return {"questions": [
        {"key": "data_materials", "question": "Какие данные вы готовы предоставить?"},
        {"key": "expected_result", "question": "Какой результат вы ждёте от команды?"},
        {"key": "success_criteria", "question": "Как вы поймёте, что решение подходит?"},
    ], "missing": ["data_materials", "expected_result", "success_criteria"], "source": "fallback"}

# core/rating.py
def calculate_rating(card):
    return {"score": 0, "level": "draft", "breakdown": [], "missing": [], "tips": []}
```

Заглушки живут максимум до 100-й минуты. В финальной версии их быть не должно —
кроме осознанного fallback в `core/ai.py`, который кейс разрешает.
