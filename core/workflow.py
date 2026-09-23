"""Human-reviewed solutions and a grounded, deterministic coaching fallback."""
import time
from core import ai, store
from core.accounts import AccountError


def submit(proposal_id, result, link, comment):
    def update(state):
        history = state.setdefault("submissions", {}).setdefault(proposal_id, [])
        if history and history[-1]["status"] in {"pending", "accepted"}:
            raise AccountError("Решение уже на проверке или принято.")
        item = {"version": len(history) + 1, "result": result, "link": link,
                "comment": comment, "status": "pending", "created_at": time.time()}
        history.append(item)
        return item
    return store.workflow_state(update)


def review(proposal_id, version, decision, comment):
    def update(state):
        history = state.get("submissions", {}).get(proposal_id, [])
        if not history or history[-1]["version"] != version or history[-1]["status"] != "pending":
            raise AccountError("Эта версия уже рассмотрена или не найдена.")
        item = history[-1]
        item.update(status=decision, feedback=comment, reviewed_at=time.time())
        return item
    return store.workflow_state(update)


def coach(task, question):
    return ai.coach_solution(task, question)
