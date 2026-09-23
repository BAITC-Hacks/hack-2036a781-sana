"""Human-reviewed solutions and a grounded, deterministic coaching fallback."""
import time
from core import store
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
    # Explicit fallback: quote only card facts, never claim generated work is a result.
    labels = {"users": "для кого решение", "data_materials": "данные и материалы",
              "constraints": "ограничения", "expected_result": "ожидаемый результат",
              "success_criteria": "критерии успеха", "contact": "контакт бизнеса"}
    missing = [label for field, label in labels.items() if not task.get(field)]
    result = "Я помогу спланировать работу, но не выполню задание за команду.\n\n"
    result += "1. Сверьте понимание задачи: «" + task.get("need", task.get("title", "")) + "».\n"
    result += "2. Проверьте доступные материалы вместе с бизнесом.\n"
    result += "3. Разбейте результат на небольшие проверяемые этапы и согласуйте первый.\n"
    result += "4. Перед отправкой сравните решение с критериями: " + (task.get("success_criteria") or "в карточке не указаны") + ".\n"
    if missing:
        result += "\nВ карточке не указано: " + ", ".join(missing) + ". Уточните это у бизнеса; я не буду придумывать ответы."
    return {"text": result, "source": "fallback"}
