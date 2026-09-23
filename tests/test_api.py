import pytest

from core import ai


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
    published = client.post("/api/tasks", json={"card": task}).json()["data"]["task"]
    assert published["status"] == "published"
    assert published["rating"]["score"] == 20
    catalog = client.get("/api/tasks?level=draft").json()["data"]["tasks"]
    assert published["id"] in {item["id"] for item in catalog}

    task["data_materials"] = "Есть обезличенные примеры работ и рубрика проверки."
    updated = client.put(f"/api/tasks/{published['id']}", json={"card": task}).json()["data"]["task"]
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
        response = client.post(f"/api/tasks/{task_id}/proposals", json=payload)
        assert response.json()["ok"] is True
        created.append(response.json()["data"]["proposal"])
    assert len(client.get(f"/api/tasks/{task_id}/proposals").json()["data"]["proposals"]) == 7
    assert all(item["status"] == "new" for item in created)

    decision = client.post(
        f"/api/proposals/{created[0]['id']}/decision", json={"decision": "accepted"}
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
    proposal = client.post("/api/tasks/t_001/proposals", json=payload).json()["data"]["proposal"]
    accepted = client.post(f"/api/proposals/{proposal['id']}/decision", json={"decision": "accepted"})
    assert accepted.json()["ok"] is True
    report = client.post(
        f"/api/proposals/{proposal['id']}/progress",
        json={"result": "Прототипті бес студентпен тексердік, төртеуі тапсырманы аяқтады.", "evidence_link": "https://example.com/result"},
    ).json()["data"]["progress"]
    assert report["status"] == "submitted"
    assert client.get("/api/progress").json()["data"]["teams"][0]["progress_points"] == 0
    confirmed = client.post(f"/api/progress/{report['id']}/decision", json={"decision": "confirmed"})
    assert confirmed.json()["data"]["progress"]["points"] == 10
    assert client.get("/api/progress").json()["data"]["teams"][0]["progress_points"] == 10
    assert client.post(f"/api/progress/{report['id']}/decision", json={"decision": "confirmed"}).json()["ok"] is False


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
