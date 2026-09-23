"""Password accounts, opaque sessions and team membership; no framework imports."""
import hashlib
import hmac
import re
import secrets
import time

from core import store

SESSION_SECONDS = 7 * 24 * 3600


class AccountError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def public(user):
    return {k: user.get(k, "") for k in ("id", "name", "email", "role", "company", "about")}


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()


def throttle(key, limit=10, seconds=900):
    now = time.time()
    def update(state):
        entries = state.setdefault("limits", {})
        for old in list(entries):
            entries[old] = [t for t in entries[old] if now - t < seconds]
            if not entries[old]:
                del entries[old]
        attempts = entries.setdefault(digest(key), [])
        if len(attempts) >= limit:
            return False
        attempts.append(now)
        return True
    if not store.workflow_state(update):
        raise AccountError("Слишком много попыток. Попробуйте через 15 минут.")


def authenticate(body, register=False):
    email = body.get("email", "")
    password = body.get("password", "")
    if not isinstance(email, str) or not re.fullmatch(r"[^\s@]{1,100}@[^\s@]{1,100}\.[^\s@]{2,30}", email.strip()):
        raise AccountError("Введите корректный email.")
    if not isinstance(password, str) or not 10 <= len(password) <= 128:
        raise AccountError("Пароль должен содержать от 10 до 128 символов.")
    email = email.strip().casefold()
    name, role = body.get("name", ""), body.get("role", "")
    if register and (not isinstance(name, str) or not 2 <= len(name.strip()) <= 80 or not isinstance(role, str) or role not in {"business", "student"}):
        raise AccountError("Укажите имя и выберите роль.")
    # Expensive hashing stays outside the storage lock.
    found = next((u for u in store.workflow_state().get("users", {}).values() if u["email"] == email), None)
    salt = found["salt"] if found and not register else secrets.token_hex(16)
    hashed = password_hash(password, salt)
    token = secrets.token_urlsafe(32)
    now = time.time()
    def update(state):
        users = state.setdefault("users", {})
        existing = next((u for u in users.values() if u["email"] == email), None)
        if register:
            if existing:
                raise AccountError("Не удалось создать аккаунт. Попробуйте войти.")
            user = {"id": secrets.token_hex(16), "name": name.strip(), "email": email,
                    "role": role, "salt": salt, "password_hash": hashed}
            users[user["id"]] = user
        else:
            if not existing or not found or not hmac.compare_digest(existing["password_hash"], hashed):
                raise AccountError("Неверный email или пароль.")
            user = existing
        sessions = state.setdefault("sessions", {})
        for key in list(sessions):
            if sessions[key]["expires"] <= now:
                del sessions[key]
        sessions[digest(token)] = {"user_id": user["id"], "expires": now + SESSION_SECONDS}
        return public(user)
    return store.workflow_state(update), token


def current(token):
    if not token or not 32 <= len(token) <= 128:
        return None
    state = store.workflow_state()
    session = state.get("sessions", {}).get(digest(token), {})
    if session.get("expires", 0) <= time.time():
        return None
    user = state.get("users", {}).get(session.get("user_id"))
    return public(user) if user else None


def logout(token):
    store.workflow_state(lambda s: s.setdefault("sessions", {}).pop(digest(token), None))


def member(user, team):
    if not user or user["role"] != "student":
        return False
    return user["id"] == team.get("creator_id") or user["id"] in store.workflow_state().get("members", {}).get(team["id"], [])


def team_details(user):
    state = store.workflow_state()
    result = []
    for team in store.load_teams():
        ids = state.get("members", {}).get(team["id"], [])
        if user["id"] != team.get("creator_id") and user["id"] not in ids:
            continue
        ids = list(dict.fromkeys([team.get("creator_id"), *ids]))
        result.append({"id": team["id"], "name": team["name"],
                       "members": [{"id": uid, "name": state["users"][uid]["name"], "captain": uid == team.get("creator_id")} for uid in ids if uid in state.get("users", {})],
                       "code": state.get("invites", {}).get(team["id"], {}).get("code", "")})
    return result


def invite(user, team):
    if team.get("creator_id") != user["id"]:
        raise AccountError("Код приглашения обновляет капитан команды.")
    def update(state):
        invites = state.setdefault("invites", {})
        used = {v["code"] for v in invites.values()}
        for _ in range(50):
            code = f"{secrets.randbelow(1000000):06d}"
            if code not in used:
                invites[team["id"]] = {"code": code, "expires": time.time() + 86400 * 7}
                return code
        raise AccountError("Попробуйте создать код ещё раз.")
    return store.workflow_state(update)


def join(user, code):
    if user["role"] != "student" or not isinstance(code, str) or not re.fullmatch(r"\d{6}", code):
        raise AccountError("Введите шестизначный код команды.")
    def update(state):
        team_id = next((key for key, value in state.get("invites", {}).items() if value["code"] == code and value["expires"] > time.time()), None)
        if not team_id:
            raise AccountError("Код неверен или истёк. Попросите капитана обновить код.")
        members = state.setdefault("members", {}).setdefault(team_id, [])
        if user["id"] not in members:
            members.append(user["id"])
        return team_id
    return store.workflow_state(update)


def claim_legacy(user, tasks, teams):
    """Recover records created before accounts, using their browser-held tokens."""
    if not isinstance(tasks, dict) or not isinstance(teams, dict) or len(tasks) > 200 or len(teams) > 200:
        raise AccountError("Слишком много записей для восстановления.")
    claimed = {"tasks": [], "teams": []}
    groups = ((tasks, "tasks"), (teams, "teams"))
    for records, kind in groups:
        for record_id, token in records.items():
            if not isinstance(record_id, str) or len(record_id) > 100 or not isinstance(token, str) or not 32 <= len(token) <= 128:
                continue
            token_hash = digest(token)
            if kind == "tasks" and user["role"] == "business":
                if store.claim_task_owner(record_id, token_hash, user["id"]):
                    claimed[kind].append(record_id)
            if kind == "teams" and user["role"] == "student":
                if store.claim_team_creator(record_id, token_hash, user["id"]):
                    claimed[kind].append(record_id)
                    store.workflow_state(lambda state: state.setdefault("members", {}).setdefault(record_id, []).append(user["id"]))
    return claimed
