from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core import ai, store
from core.rating import calculate_rating


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = Path(__file__).resolve().parent / "static"
TASK_FIELDS = (
    "title",
    "context",
    "need",
    "users",
    "data_materials",
    "constraints",
    "expected_result",
    "success_criteria",
    "contact",
    "interaction_format",
)
MAX_TEXT_LENGTH = 4000
MAX_PROPOSAL_TEXT_LENGTH = 2000
PROGRESS_POINTS_PER_CONFIRMED_STAGE = 10

app = FastAPI(
    title="Sana",
    description="Практикалық білім міндеттерінің ашық каталогы",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


def _success(data: dict) -> JSONResponse:
    return JSONResponse(status_code=200, content={"ok": True, "data": data})


def _failure(code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={"ok": False, "error": {"code": code, "message": message}},
    )


async def _read_body(request: Request) -> Union[dict, JSONResponse]:
    try:
        body = await request.json()
    except Exception:
        return _failure("invalid_input", "Тело запроса должно быть корректным JSON.")
    if not isinstance(body, dict):
        return _failure("invalid_input", "Ожидался JSON-объект.")
    return body


def _validate_card(raw_card: Any) -> Union[dict, JSONResponse]:
    if not isinstance(raw_card, dict):
        return _failure("invalid_input", "Карточка должна быть JSON-объектом.")
    card = {}
    for field in TASK_FIELDS:
        value = raw_card.get(field, "")
        if not isinstance(value, str):
            return _failure("invalid_input", f"Поле «{field}» должно быть текстом.")
        value = value.strip()
        if len(value) > MAX_TEXT_LENGTH:
            return _failure("invalid_input", f"Поле «{field}» слишком длинное.")
        card[field] = value

    industry = raw_card.get("industry", "")
    if not isinstance(industry, str) or len(industry.strip()) > 80:
        return _failure("invalid_input", "Укажите корректную тему задачи.")
    card["industry"] = industry.strip()
    if not card["title"]:
        return _failure("invalid_input", "Укажите название задачи.")
    if not card["industry"]:
        return _failure("invalid_input", "Выберите тему задачи.")
    return card


def _validate_text(value: Any, field: str, max_length: int) -> Union[str, JSONResponse]:
    if not isinstance(value, str) or not value.strip():
        return _failure("invalid_input", f"Заполните поле «{field}».")
    normalized = value.strip()
    if len(normalized) > max_length:
        return _failure("invalid_input", f"Поле «{field}» слишком длинное.")
    return normalized


def _safe_link(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _locale(body: dict) -> Union[str, JSONResponse]:
    language = body.get("locale", "ru")
    if not isinstance(language, str) or language not in {"ru", "kk", "en"}:
        return _failure("invalid_input", "Язык должен быть ru, kk или en.")
    return language


def _error_from_result(result: dict) -> Optional[JSONResponse]:
    error = result.get("error") if isinstance(result, dict) else None
    if not isinstance(error, dict):
        return None
    return _failure(
        str(error.get("code", "invalid_input")),
        str(error.get("message", "Проверьте введённые данные.")),
    )


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(request: Request) -> JSONResponse:
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    draft = body.get("draft")
    industry = body.get("industry", "")
    language = _locale(body)
    if isinstance(language, JSONResponse):
        return language
    result = ai.analyze_draft(draft, industry, language)
    error = _error_from_result(result)
    return error or _success(result)


@app.post("/api/build-card")
async def build_card(request: Request) -> JSONResponse:
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    language = _locale(body)
    if isinstance(language, JSONResponse):
        return language
    result = ai.build_card(body.get("draft"), body.get("answers", []), language)
    error = _error_from_result(result)
    if error:
        return error
    card = result.get("card")
    industry = body.get("industry", "")
    if isinstance(card, dict) and isinstance(industry, str) and len(industry) <= 80:
        card["industry"] = industry.strip()
        card["rating"] = calculate_rating(card)
    return _success(result)


@app.post("/api/rating")
async def rating(request: Request) -> JSONResponse:
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    card = body.get("card")
    if not isinstance(card, dict):
        return _failure("invalid_input", "Передайте карточку для расчёта рейтинга.")
    return _success({"rating": calculate_rating(card)})


@app.post("/api/tasks")
async def create_task(request: Request) -> JSONResponse:
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    card = _validate_card(body.get("card"))
    if isinstance(card, JSONResponse):
        return card
    card["rating"] = calculate_rating(card)
    card["status"] = "published"
    saved = store.save_task(card)
    if not saved or not store.get_task(saved.get("id", "")):
        return _failure("internal_error", "Не удалось сохранить задачу. Повторите попытку.")
    return _success({"task": saved})


@app.get("/api/tasks")
def list_tasks(
    industry: Optional[str] = None,
    level: Optional[str] = None,
    sort: str = "rating",
) -> JSONResponse:
    if level and level not in {"draft", "working", "ready", "priority"}:
        return _failure("invalid_input", "Неизвестный уровень готовности.")
    if sort not in {"rating", "date"}:
        return _failure("invalid_input", "Сортировка должна быть rating или date.")
    tasks = [task for task in store.load_tasks() if task.get("status") == "published"]
    if industry:
        tasks = [task for task in tasks if task.get("industry") == industry]
    if level:
        tasks = [task for task in tasks if task.get("rating", {}).get("level") == level]
    if sort == "date":
        tasks.sort(key=lambda task: str(task.get("created_at", "")), reverse=True)
    else:
        tasks.sort(key=lambda task: task.get("rating", {}).get("score", 0), reverse=True)
    return _success({"tasks": tasks})


@app.get("/api/tasks/{task_id}")
def task_detail(task_id: str) -> JSONResponse:
    task = store.get_task(task_id)
    if task is None:
        return _failure("not_found", "Задача не найдена.")
    return _success({"task": task})


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, request: Request) -> JSONResponse:
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    existing = store.get_task(task_id)
    if existing is None:
        return _failure("not_found", "Задача не найдена.")
    card = _validate_card(body.get("card"))
    if isinstance(card, JSONResponse):
        return card
    card["status"] = existing.get("status", "draft")
    card["rating"] = calculate_rating(card)
    updated = store.update_task(task_id, card)
    if updated is None:
        return _failure("internal_error", "Не удалось сохранить изменения задачи.")
    return _success({"task": updated})


@app.get("/api/teams")
def list_teams() -> JSONResponse:
    return _success({"teams": store.load_teams()})


@app.get("/api/demo")
def demo_example() -> JSONResponse:
    example = store.load_demo()
    if not example:
        return _failure("not_found", "Демонстрационный пример не найден.")
    return _success(example)


@app.post("/api/tasks/{task_id}/proposals")
async def create_proposal(task_id: str, request: Request) -> JSONResponse:
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    task = store.get_task(task_id)
    if task is None or task.get("status") != "published":
        return _failure("not_found", "Опубликованная задача не найдена.")

    team_id = body.get("team_id")
    if not isinstance(team_id, str) or not any(
        team.get("id") == team_id for team in store.load_teams()
    ):
        return _failure("invalid_input", "Выберите существующую команду.")

    required_fields = {
        "idea": "идею решения",
        "plan": "план работы",
        "deadline": "срок",
        "link": "ссылку на прототип",
    }
    proposal = {"task_id": task_id, "team_id": team_id}
    for field, label in required_fields.items():
        value = _validate_text(body.get(field), label, MAX_PROPOSAL_TEXT_LENGTH)
        if isinstance(value, JSONResponse):
            return value
        proposal[field] = value
    if not _safe_link(proposal["link"]):
        return _failure("invalid_input", "Ссылка должна начинаться с http:// или https://.")

    saved = store.save_proposal(proposal)
    if not saved or not any(item.get("id") == saved.get("id") for item in store.load_proposals(task_id)):
        return _failure("internal_error", "Не удалось сохранить предложение.")
    return _success({"proposal": saved})


@app.get("/api/tasks/{task_id}/proposals")
def list_task_proposals(task_id: str) -> JSONResponse:
    if store.get_task(task_id) is None:
        return _failure("not_found", "Задача не найдена.")
    return _success({"proposals": store.load_proposals(task_id)})


@app.post("/api/proposals/{proposal_id}/decision")
async def decide_proposal(proposal_id: str, request: Request) -> JSONResponse:
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    decision = body.get("decision")
    if decision not in {"accepted", "rejected"}:
        return _failure("invalid_input", "Решение должно быть accepted или rejected.")
    proposal = store.update_proposal_status(proposal_id, decision)
    if proposal is None:
        return _failure("not_found", "Предложение не найдено.")
    return _success({"proposal": proposal})


@app.post("/api/proposals/{proposal_id}/progress")
async def submit_progress(proposal_id: str, request: Request) -> JSONResponse:
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    proposal = next(
        (item for item in store.load_proposals() if item.get("id") == proposal_id), None
    )
    if proposal is None or proposal.get("status") != "accepted":
        return _failure("invalid_input", "Прогресс можно добавить только выбранной команды.")
    result_text = _validate_text(body.get("result"), "фактический результат этапа", MAX_PROPOSAL_TEXT_LENGTH)
    if isinstance(result_text, JSONResponse):
        return result_text
    evidence_link = _validate_text(body.get("evidence_link"), "ссылку на доказательство", 500)
    if isinstance(evidence_link, JSONResponse):
        return evidence_link
    if not _safe_link(evidence_link):
        return _failure("invalid_input", "Ссылка на доказательство должна начинаться с http:// или https://.")
    saved = store.save_progress({
        "proposal_id": proposal_id,
        "task_id": proposal["task_id"],
        "team_id": proposal["team_id"],
        "result": result_text,
        "evidence_link": evidence_link,
    })
    if not saved:
        return _failure("internal_error", "Не удалось отправить отчёт о прогрессе.")
    return _success({"progress": saved})


@app.get("/api/proposals/{proposal_id}/progress")
def list_proposal_progress(proposal_id: str) -> JSONResponse:
    if not any(item.get("id") == proposal_id for item in store.load_proposals()):
        return _failure("not_found", "Предложение не найдено.")
    entries = [item for item in store.load_progress() if item.get("proposal_id") == proposal_id]
    return _success({"progress": entries})


@app.post("/api/progress/{progress_id}/decision")
async def decide_progress(progress_id: str, request: Request) -> JSONResponse:
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    decision = body.get("decision")
    if decision not in {"confirmed", "rejected"}:
        return _failure("invalid_input", "Результат проверки должен быть confirmed или rejected.")
    entry = store.update_progress_status(
        progress_id,
        decision,
        PROGRESS_POINTS_PER_CONFIRMED_STAGE if decision == "confirmed" else 0,
    )
    if entry is None:
        return _failure("not_found", "Неотправленный отчёт прогресса не найден.")
    return _success({"progress": entry})


@app.get("/api/progress")
def progress_leaderboard() -> JSONResponse:
    points_by_team = {}
    for item in store.load_progress():
        if item.get("status") == "confirmed":
            team_id = item.get("team_id")
            points_by_team[team_id] = points_by_team.get(team_id, 0) + int(item.get("points", 0))
    teams = []
    for team in store.load_teams():
        teams.append({**team, "progress_points": points_by_team.get(team.get("id"), 0)})
    teams.sort(key=lambda team: (-team["progress_points"], team.get("name", "")))
    return _success({"teams": teams, "points_per_confirmed_stage": PROGRESS_POINTS_PER_CONFIRMED_STAGE})


@app.get("/api/recommendations")
def recommendations(team_id: str) -> JSONResponse:
    team = next((item for item in store.load_teams() if item.get("id") == team_id), None)
    if team is None:
        return _failure("not_found", "Команда не найдена.")
    interests = [str(value).casefold() for value in team.get("interests", [])]
    skills = [str(value).casefold() for value in team.get("skills", [])]
    technologies = [str(value).casefold() for value in team.get("technologies", [])]
    tasks = [task for task in store.load_tasks() if task.get("status") == "published"]

    def relevance(task: dict) -> tuple[int, int]:
        content = " ".join(
            str(task.get(field, ""))
            for field in ("industry", "title", "context", "need", "expected_result")
        ).casefold()
        matches = sum(term in content for term in interests + skills + technologies if term)
        score = task.get("rating", {}).get("score", 0)
        return matches, score if isinstance(score, int) else 0

    tasks.sort(key=relevance, reverse=True)
    reasons = {
        task["id"]: {"matched_profile_terms": relevance(task)[0]}
        for task in tasks
    }
    return _success({"tasks": tasks[:3], "reason": reasons})


@app.exception_handler(Exception)
async def unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
    LOGGER.exception("Необработанная ошибка приложения", exc_info=exc)
    return _failure("internal_error", "Не удалось выполнить запрос. Попробуйте ещё раз.")
