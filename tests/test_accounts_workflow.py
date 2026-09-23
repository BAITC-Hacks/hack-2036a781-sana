from fastapi.testclient import TestClient
from app.main import app
from core import store, accounts


def test_accounts_and_full_delivery(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DATABASE_URL", "")
    monkeypatch.setenv("SANA_LEGACY_MODE", "0")
    business = TestClient(app, headers={"X-Sana-Request": "1"})
    student = TestClient(app, headers={"X-Sana-Request": "1"})
    friend = TestClient(app, headers={"X-Sana-Request": "1"})
    stranger = TestClient(app, headers={"X-Sana-Request": "1"})
    def post(client, path, values):
        response = client.post(path, json=values)
        assert response.json().get("ok"), response.text
        return response.json()["data"]
    for client, role, email in [(business,"business","business@example.com"),(student,"student","student@example.com"),(friend,"student","friend@example.com"),(stranger,"business","other@example.com")]:
        post(client,"/api/auth/register",{"name":"Test User","email":email,"password":"correct-password-123","role":role})
    assert TestClient(app).post("/api/teams",json={"name":"Oops"}).status_code == 403
    assert TestClient(app).get("/api/workspaces").status_code == 401
    assert student.post("/api/tasks",json={}).status_code == 403
    assert business.post("/api/teams",json={"name":"Oops"}).status_code == 403
    assert student.post("/api/auth/login",json={"email":"student@example.com","password":"incorrect-password"}).status_code == 400
    assert student.get("/api/auth/me").json()["data"]["user"]["role"] == "student"
    team=post(student,"/api/teams",{"name":"Makers"})["team"]
    code=post(student,f"/api/account/teams/{team['id']}/invite",{})["code"]
    assert len(code)==6 and code.isdigit()
    post(friend,"/api/account/join",{"code":code})
    assert len(friend.get("/api/auth/me").json()["data"]["teams"][0]["members"])==2
    assert friend.post(f"/api/account/teams/{team['id']}/invite",json={}).status_code==400
    card={"title":"Нужен сайт", "industry":"other"}
    task=post(business,"/api/tasks",{"card":card})["task"]
    task_id=task["id"]
    assert not stranger.put(f"/api/tasks/{task_id}",json={"card":card}).json()["ok"]
    proposal=post(friend,f"/api/tasks/{task_id}/proposals",{"team_id":team["id"],"idea":"Идея","plan":"План","deadline":"14 дней","link":"https://example.com/demo"})["proposal"]
    pid=proposal["id"]
    assert friend.post(f"/api/workspaces/{pid}/submit",json={}).status_code==400
    post(business,f"/api/proposals/{pid}/decision",{"decision":"accepted"})
    assert len(friend.get("/api/workspaces").json()["data"]["workspaces"])==1
    assert stranger.get("/api/workspaces").json()["data"]["workspaces"]==[]
    solution={"result":"Прототип готов","link":"https://example.com/result","comment":"Проверьте"}
    post(friend,f"/api/workspaces/{pid}/submit",solution)
    assert student.post(f"/api/workspaces/{pid}/submit",json=solution).status_code==400
    assert business.post(f"/api/workspaces/{pid}/review",json={"version":1,"decision":"returned","comment":""}).status_code==400
    post(business,f"/api/workspaces/{pid}/review",{"version":1,"decision":"returned","comment":"Добавьте мобильную версию"})
    post(student,f"/api/workspaces/{pid}/submit",solution)
    post(business,f"/api/workspaces/{pid}/review",{"version":2,"decision":"accepted","comment":"Спасибо"})
    history=student.get("/api/workspaces").json()["data"]["workspaces"][0]["history"]
    assert [x["status"] for x in history]==["returned","accepted"]
    assert student.post(f"/api/workspaces/{pid}/submit",json=solution).status_code==400
    assert friend.post(f"/api/workspaces/{pid}/review",json={"version":2,"decision":"accepted"}).status_code==403
    answer=post(student,f"/api/workspaces/{pid}/coach",{"question":"Напиши весь код"})
    assert answer["messages"][-1]["source"]=="fallback"
    assert "не выполню" in answer["messages"][-1]["text"]
    notifications=business.get("/api/notifications").json()["data"]["notifications"]
    assert notifications
    post(business,"/api/notifications/read",{"ids":[n["id"] for n in notifications]})
    assert all(n["read"] for n in business.get("/api/notifications").json()["data"]["notifications"])
    token=student.cookies.get("sana_session")
    post(student,"/api/auth/logout",{})
    assert accounts.current(token) is None
    post(student,"/api/auth/login",{"email":"student@example.com","password":"correct-password-123"})
    assert student.get("/api/auth/me").json()["data"]["teams"]
    state=store.workflow_state()
    assert "correct-password-123" not in str(state)
    assert token not in state["sessions"]


def test_csrf_and_rate_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(store,"DATA_DIR",tmp_path)
    monkeypatch.setattr(store,"DATABASE_URL","")
    monkeypatch.setenv("SANA_LEGACY_MODE","0")
    client=TestClient(app,headers={"X-Sana-Request":"1","Origin":"https://attacker.example"})
    assert client.post("/api/auth/register",json={}).status_code==403
    for _ in range(2):
        accounts.throttle("test",limit=2)
    try:
        accounts.throttle("test",limit=2)
        assert False, "Expected rate limit"
    except accounts.AccountError:
        pass
