import pytest
from concurrent.futures import ThreadPoolExecutor

from core import ai, store
from conftest import TEST_OWNER_TOKEN, TEST_TEAM_TOKEN


OWNER_HEADERS = {"X-Sana-Owner": TEST_OWNER_TOKEN}
TEAM_HEADERS = {"X-Sana-Team": TEST_TEAM_TOKEN}


def test_health_and_home(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    home = client.get("/")
    assert home.status_code == 200
    assert "Sana" in home.text


def test_analyze_returns_three_fallback_questions(client):
    response = client.post(
        "/api/analyze",
        json={"draft": "В школе нужно улучшить практические занятия.", "industry": "school"},
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["source"] == "fallback"
    assert len(result["questions"]) >= 3


@pytest.mark.parametrize(
    ("locale", "expected"),
    [("ru", "Что происходит"), ("kk", "Қазір не болып"), ("en", "What is happening")],
)
def test_analyze_fallback_uses_selected_language(client, locale, expected):
    result = client.post(
        "/api/analyze",
        json={"draft": "A school needs to improve practical learning activities.", "locale": locale},
    ).json()["data"]
    assert result["source"] == "fallback"
    assert len(result["questions"]) >= 3
    assert expected in result["questions"][0]["question"]


def test_fallback_mode_never_calls_model(client, monkeypatch):
    monkeypatch.setenv("AI_MODE", "fallback")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Модель не должна вызываться в режиме fallback")

    monkeypatch.setattr(ai, "OpenAI", forbidden)
    result = client.post(
        "/api/analyze",
        json={"draft": "Школа хочет улучшить практические задания.", "industry": "school"},
    ).json()["data"]
    assert result["source"] == "fallback"
    assert len(result["questions"]) >= 3


def test_analyze_rejects_invalid_input_using_contract_wrapper(client):
    response = client.post("/api/analyze", json={"draft": "  "})
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"]["code"] == "invalid_input"


def test_publish_low_score_task_and_edit_recalculates(client):
    task = {
        "title": "Проверка задач по Python",
        "industry": "online_school",
        "context": "Учителя проверяют задания вручную каждый день.",
        "need": "Нужно сократить время проверки в учебном процессе.",
    }
    created = client.post("/api/tasks", json={"card": task}).json()["data"]
    published = created["task"]
    assert published["status"] == "published"
    assert published["rating"]["score"] == 20
    catalog = client.get("/api/tasks?level=draft").json()["data"]["tasks"]
    assert published["id"] in {item["id"] for item in catalog}

    task["data_materials"] = "Есть обезличенные примеры работ и рубрика проверки."
    updated = client.put(
        f"/api/tasks/{published['id']}",
        json={"card": task},
        headers={"X-Sana-Owner": created["owner_token"]},
    ).json()["data"]["task"]
    assert updated["rating"]["score"] == 40
    assert updated["status"] == "published"


def test_low_score_task_accepts_unlimited_proposals_and_manual_decisions(client):
    task_id = "t_001"
    payload = {
        "team_id": "team_01",
        "idea": "Собрать прототип обратной связи для преподавателя.",
        "plan": "Проверить сценарий на синтетических примерах и показать методисту.",
        "deadline": "2 недели",
        "link": "https://example.com/prototype",
    }
    created = []
    for _ in range(6):
        response = client.post(f"/api/tasks/{task_id}/proposals", json=payload, headers=TEAM_HEADERS)
        assert response.json()["ok"] is True
        created.append(response.json()["data"]["proposal"])
    assert len(client.get(f"/api/tasks/{task_id}/proposals", headers=OWNER_HEADERS).json()["data"]["proposals"]) == 7
    assert all(item["status"] == "new" for item in created)

    decision = client.post(
        f"/api/proposals/{created[0]['id']}/decision", json={"decision": "accepted"}, headers=OWNER_HEADERS
    )
    assert decision.json()["data"]["proposal"]["status"] == "accepted"


def test_confirmed_factual_progress_awards_points_once(client):
    payload = {
        "team_id": "team_01",
        "idea": "Жасау",
        "plan": "Сынақтан өткізу",
        "deadline": "2 апта",
        "link": "https://example.com/prototype",
    }
    proposal = client.post("/api/tasks/t_001/proposals", json=payload, headers=TEAM_HEADERS).json()["data"]["proposal"]
    accepted = client.post(f"/api/proposals/{proposal['id']}/decision", json={"decision": "accepted"}, headers=OWNER_HEADERS)
    assert accepted.json()["ok"] is True
    report = client.post(
        f"/api/proposals/{proposal['id']}/progress",
        json={"result": "Прототипті бес студентпен тексердік, төртеуі тапсырманы аяқтады.", "evidence_link": "https://example.com/result"},
        headers=TEAM_HEADERS,
    ).json()["data"]["progress"]
    assert report["status"] == "submitted"
    assert client.get("/api/progress").json()["data"]["teams"][0]["progress_points"] == 0
    confirmed = client.post(f"/api/progress/{report['id']}/decision", json={"decision": "confirmed"}, headers=OWNER_HEADERS)
    assert confirmed.json()["data"]["progress"]["points"] == 10
    assert client.get("/api/progress").json()["data"]["teams"][0]["progress_points"] == 10
    assert client.post(f"/api/progress/{report['id']}/decision", json={"decision": "confirmed"}, headers=OWNER_HEADERS).json()["ok"] is False


def test_invalid_proposal_and_missing_task_are_clear(client):
    invalid = client.post(
        "/api/tasks/t_001/proposals",
        json={"team_id": "unknown", "idea": "x", "plan": "x", "deadline": "x", "link": "javascript:alert(1)"},
    )
    assert invalid.json()["ok"] is False
    assert client.get("/api/tasks/unknown").json()["error"]["code"] == "not_found"


def test_filters_do_not_change_full_open_catalog(client):
    all_tasks = client.get("/api/tasks").json()["data"]["tasks"]
    filtered = client.get("/api/tasks?industry=university").json()["data"]["tasks"]
    assert len(all_tasks) == 5
    assert filtered
    assert all(task["industry"] == "university" for task in filtered)
    recommended = client.get("/api/recommendations?team_id=team_01").json()["data"]["tasks"]
    assert len(recommended) <= 3
    assert len(client.get("/api/tasks").json()["data"]["tasks"]) == 5


def test_fresh_real_user_flow_and_private_decisions(fresh_client):
    browser = fresh_client
    assert browser.get("/api/tasks").json()["data"]["tasks"] == []
    assert browser.get("/api/teams").json()["data"]["teams"] == []

    draft = "Учителям сложно вовремя проверять практические задания по Python."
    analysis = browser.post("/api/analyze", json={"draft": draft, "industry": "school"}).json()["data"]
    assert len(analysis["questions"]) >= 3
    answers = [{"key": item["key"], "answer": ""} for item in analysis["questions"]]
    built = browser.post("/api/build-card", json={"draft": draft, "industry": "school", "answers": answers}).json()["data"]["card"]
    assert built["context"] == draft
    assert built["data_materials"] == ""

    built.update({
        "need": "Ускорить проверку работ и обратную связь ученикам.",
        "users": "Учителя и ученики средней школы.",
        "data_materials": "Обезличенные работы и критерии проверки.",
        "constraints": "Срок четыре недели; данные без персональных сведений.",
        "expected_result": "Рабочий прототип сервиса с интерфейсом проверки.",
        "success_criteria": "Время проверки сокращается минимум на треть.",
        "contact": "Методист школы, контакт через рабочую почту.",
        "interaction_format": "Одна консультация в неделю и письменная обратная связь.",
    })
    rated = browser.post("/api/rating", json={"card": built}).json()["data"]["rating"]
    assert rated["score"] == 100
    created = browser.post("/api/tasks", json={"card": built}).json()["data"]
    task, owner_token = created["task"], created["owner_token"]
    assert "owner_token_hash" not in task
    assert "owner_token_hash" not in browser.get("/api/tasks").json()["data"]["tasks"][0]
    assert browser.get(f"/api/tasks/{task['id']}/proposals").json()["error"]["code"] == "forbidden"
    assert browser.put(f"/api/tasks/{task['id']}", json={"card": built}).json()["error"]["code"] == "forbidden"

    team_created = browser.post("/api/teams", json={
        "name": "Sana students", "interests": ["education"],
        "skills": ["Python"], "technologies": ["FastAPI"],
    }).json()["data"]
    team, team_token = team_created["team"], team_created["team_token"]
    assert "team_token_hash" not in team
    payload = {
        "team_id": team["id"], "idea": "Собрать понятный прототип проверки заданий.",
        "plan": "Изучить процесс, собрать прототип, провести проверку.",
        "deadline": "Четыре недели", "link": "https://example.org/prototype",
    }
    url = f"/api/tasks/{task['id']}/proposals"
    assert browser.post(url, json=payload).json()["error"]["code"] == "forbidden"
    proposal = browser.post(url, json=payload, headers={"X-Sana-Team": team_token}).json()["data"]["proposal"]
    assert browser.get(f"/api/teams/{team['id']}/proposals", headers={"X-Sana-Team": team_token}).json()["data"]["proposals"][0]["id"] == proposal["id"]
    assert browser.post(f"/api/proposals/{proposal['id']}/decision", json={"decision": "accepted"}).json()["error"]["code"] == "forbidden"
    assert browser.post(f"/api/proposals/{proposal['id']}/decision", json={"decision": "accepted"}, headers={"X-Sana-Owner": owner_token}).json()["data"]["proposal"]["status"] == "accepted"
    report = browser.post(f"/api/proposals/{proposal['id']}/progress", json={
        "result": "Прототип проверен на шести работах с согласия методиста.",
        "evidence_link": "https://example.org/result",
    }, headers={"X-Sana-Team": team_token}).json()["data"]["progress"]
    assert browser.post(f"/api/progress/{report['id']}/decision", json={"decision": "confirmed"}).json()["error"]["code"] == "forbidden"
    assert browser.post(f"/api/progress/{report['id']}/decision", json={"decision": "confirmed"}, headers={"X-Sana-Owner": owner_token}).json()["data"]["progress"]["points"] == 10
    assert browser.get("/api/progress").json()["data"]["teams"][0]["progress_points"] == 10


def test_parallel_proposals_keep_unique_ids_and_all_records(fresh_client):
    def save(index):
        return store.save_proposal({"task_id": "t_001", "team_id": "team_001", "idea": f"Идея {index}"})["id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(save, range(24)))
    assert len(set(ids)) == 24
    assert len(store.load_proposals()) == 24


def test_failed_json_write_is_reported_as_error(fresh_client, monkeypatch):
    monkeypatch.setattr(store, "_write_items", lambda _path, _items: False)
    response = fresh_client.post("/api/tasks", json={"card": {"title": "Задача", "industry": "school"}})
    assert response.json()["error"]["code"] == "internal_error"
    assert store.load_tasks() == []
