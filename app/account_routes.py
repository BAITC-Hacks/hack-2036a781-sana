"""Account and delivery routes; existing task/proposal contracts stay intact."""
from urllib.parse import urlparse
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core import accounts, store, workflow

router = APIRouter()
COOKIE = "sana_session"


def success(data):
    return JSONResponse({"ok": True, "data": data})


def fail(message, status=400):
    return JSONResponse({"ok": False, "error": {"code": "account_error", "message": message}}, status_code=status)


async def body(request):
    try:
        value = await request.json()
    except Exception:
        raise accounts.AccountError("Ожидался JSON.")
    if not isinstance(value, dict):
        raise accounts.AccountError("Ожидался JSON-объект.")
    return value


def text(value, label, required=True, limit=4000):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise accounts.AccountError("Проверьте поле: " + label)
    return value.strip()


def account_data(user):
    return {"user": user, "teams": accounts.team_details(user) if user else [],
            "owned_task_ids": [t["id"] for t in store.load_tasks() if user and t.get("owner_id") == user["id"]]}


@router.post("/api/auth/{action}")
async def auth(action: str, request: Request):
    if action == "logout":
        accounts.logout(request.cookies.get(COOKIE, ""))
        response = success({})
        response.delete_cookie(COOKIE, path="/")
        return response
    if action not in {"login", "register"}:
        return fail("Неизвестное действие.", 404)
    values = await body(request)
    accounts.throttle("auth:" + (request.client.host if request.client else "unknown"), limit=30)
    accounts.throttle("email:" + str(values.get("email", "")).strip().casefold())
    user, token = accounts.authenticate(values, register=action == "register")
    accounts.logout(request.cookies.get(COOKIE, ""))
    response = success(account_data(user))
    response.set_cookie(COOKIE, token, max_age=accounts.SESSION_SECONDS, httponly=True,
                        secure=request.url.scheme == "https", samesite="strict", path="/")
    return response


@router.get("/api/auth/me")
def me(request: Request):
    return success(account_data(request.state.user))


@router.put("/api/account/profile")
async def profile(request: Request):
    values = await body(request)
    clean = {key: text(values.get(key, ""), key, key == "name", 500) for key in ("name", "company", "about")}
    def update(state):
        user = state["users"][request.state.user["id"]]
        user.update(clean)
        return accounts.public(user)
    return success({"user": store.workflow_state(update)})


@router.post("/api/account/join")
async def join(request: Request):
    accounts.throttle("join:" + request.state.user["id"])
    team_id = accounts.join(request.state.user, (await body(request)).get("code"))
    return success({**account_data(request.state.user), "team_id": team_id})


@router.post("/api/account/teams/{team_id}/invite")
def invite(team_id: str, request: Request):
    team = store.get_team(team_id)
    if not team:
        return fail("Команда не найдена.", 404)
    return success({"code": accounts.invite(request.state.user, team)})


def allowed_proposals(user):
    tasks = {t["id"]: t for t in store.load_tasks()}
    teams = {t["id"] for t in accounts.team_details(user)}
    return [p for p in store.load_proposals() if tasks.get(p["task_id"], {}).get("owner_id") == user["id"] or p["team_id"] in teams]


def workspace(proposal_id, user):
    proposal = next((p for p in allowed_proposals(user) if p["id"] == proposal_id and p["status"] == "accepted"), None)
    if not proposal:
        raise accounts.AccountError("Рабочее пространство недоступно. Сначала бизнес должен выбрать команду.")
    return proposal


@router.get("/api/workspaces")
def workspaces(request: Request):
    state = store.workflow_state()
    items = []
    for proposal in allowed_proposals(request.state.user):
        if proposal["status"] != "accepted":
            continue
        task = store.get_task(proposal["task_id"])
        task = {k: v for k, v in task.items() if k not in {"owner_token_hash", "owner_id"}}
        items.append({"proposal": proposal, "task": task,
                      "history": state.get("submissions", {}).get(proposal["id"], []),
                      "messages": state.get("coach", {}).get(proposal["id"], [])})
    return success({"workspaces": items})


@router.post("/api/workspaces/{proposal_id}/submit")
async def submit(proposal_id: str, request: Request):
    user = request.state.user
    workspace(proposal_id, user)
    if user["role"] != "student":
        return fail("Решение отправляет команда.", 403)
    values = await body(request)
    result = text(values.get("result"), "результат")
    link = text(values.get("link"), "ссылка", limit=1000)
    parsed = urlparse(link)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return fail("Укажите ссылку http:// или https://.")
    comment = text(values.get("comment", ""), "комментарий", False)
    return success({"submission": workflow.submit(proposal_id, result, link, comment)})


@router.post("/api/workspaces/{proposal_id}/review")
async def review(proposal_id: str, request: Request):
    user = request.state.user
    workspace(proposal_id, user)
    if user["role"] != "business":
        return fail("Решение проверяет бизнес.", 403)
    values = await body(request)
    decision = values.get("decision")
    if not isinstance(decision, str) or decision not in {"accepted", "returned"} or type(values.get("version")) is not int:
        return fail("Выберите решение и версию.")
    comment = text(values.get("comment", ""), "комментарий для команды", decision == "returned")
    return success({"submission": workflow.review(proposal_id, values["version"], decision, comment)})


@router.post("/api/workspaces/{proposal_id}/coach")
async def coach(proposal_id: str, request: Request):
    proposal = workspace(proposal_id, request.state.user)
    question = text((await body(request)).get("question"), "вопрос", limit=2000)
    answer = workflow.coach(store.get_task(proposal["task_id"]), question)
    def update(state):
        messages = state.setdefault("coach", {}).setdefault(proposal_id, [])
        messages.extend([{"role": "user", "text": question}, {"role": "assistant", **answer}])
        del messages[:-100]
        return messages
    return success({"messages": store.workflow_state(update)})


@router.get("/api/notifications")
def notifications(request: Request):
    user = request.state.user
    state = store.workflow_state()
    read = state.get("read_notifications", {}).get(user["id"], [])
    events = []
    for p in allowed_proposals(user):
        if user["role"] == "business":
            events.append({"id": "proposal:" + p["id"], "text": "Получено предложение команды", "view": "offers"})
        elif p["status"] != "new":
            events.append({"id": "decision:" + p["id"], "text": "Предложение: " + ("выбрано" if p["status"] == "accepted" else "отклонено"), "view": "delivery" if p["status"] == "accepted" else "offers"})
        for item in state.get("submissions", {}).get(p["id"], []):
            if user["role"] == "business" or item["status"] != "pending":
                events.append({"id": f"solution:{p['id']}:{item['version']}:{item['status']}",
                               "text": f"Версия {item['version']}: " + {"pending": "на проверке", "returned": "нужны правки", "accepted": "принята"}[item["status"]], "view": "delivery"})
    return success({"notifications": [{**e, "read": e["id"] in read} for e in events][::-1]})


@router.post("/api/notifications/read")
async def read_notifications(request: Request):
    ids = (await body(request)).get("ids")
    if not isinstance(ids, list) or len(ids) > 1000 or any(not isinstance(x, str) or len(x) > 200 for x in ids):
        return fail("Некорректные уведомления.")
    def update(state):
        values = state.setdefault("read_notifications", {}).setdefault(request.state.user["id"], [])
        values[:] = list(dict.fromkeys([*values, *ids]))[-5000:]
    store.workflow_state(update)
    return success({})
