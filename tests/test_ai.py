from types import SimpleNamespace

from core import ai


def test_responses_api_uses_best_model_reasoning_and_structured_output(monkeypatch):
    captured = {}
    parsed = ai.AnalyzeModelResponse(
        questions=[
            {"key": "data_materials", "question": "Какие данные доступны?", "suggestions": ["Есть примеры.", "Есть описание.", "Данных пока нет."]},
            {"key": "expected_result", "question": "Какой результат нужен?", "suggestions": ["Рабочий прототип.", "Исследование.", "План внедрения."]},
            {"key": "success_criteria", "question": "Как измерить успех?", "suggestions": ["Работа выполняется быстрее.", "Меньше ошибок.", "Заказчик принимает результат."]},
        ]
    )

    class FakeResponses:
        def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_parsed=parsed)

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(ai, "_client", lambda: fake_client)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)

    result = ai._ask_model("system", {"draft": "Черновик"}, ai.AnalyzeModelResponse)

    assert result == parsed.model_dump()
    assert captured["model"] == "gpt-6-astra"
    assert captured["reasoning"] == {"effort": "max"}
    assert captured["text_format"] is ai.AnalyzeModelResponse
    assert captured["store"] is False


def test_invalid_reasoning_settings_are_safely_bounded(monkeypatch):
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "unknown")
    monkeypatch.setenv("OPENAI_MAX_OUTPUT_TOKENS", "999999")

    assert ai._reasoning_effort() == "max"
    assert ai._max_output_tokens() == 16000


def test_provider_failure_keeps_local_fallback(monkeypatch):
    class FailingResponses:
        def parse(self, **_kwargs):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        ai,
        "_client",
        lambda: SimpleNamespace(responses=FailingResponses()),
    )

    result = ai.analyze_draft("Нужно улучшить проверку практических заданий.")

    assert result["source"] == "fallback"
    assert len(result["questions"]) >= 3
    assert all(len(item["suggestions"]) == 3 for item in result["questions"])


def test_ai_field_editor_uses_selection_and_instruction(monkeypatch):
    captured = {}

    def fake_ask(system_prompt, payload, response_type, reasoning_effort=None):
        captured.update(payload)
        assert response_type is ai.EditFieldResponse
        assert reasoning_effort == "high"
        return {"text": "Проверять работы за один день."}

    monkeypatch.setattr(ai, "_ask_model", fake_ask)
    result = ai.edit_card_field(
        "success_criteria",
        "Проверять работы быстро.",
        "Уточни срок: один день",
        "быстро",
    )

    assert result == {"text": "Проверять работы за один день.", "source": "ai"}
    assert captured["selected_text"] == "быстро"


def test_ai_field_editor_rejects_unknown_selection(monkeypatch):
    monkeypatch.setattr(ai, "_ask_model", lambda *_args, **_kwargs: None)
    result = ai.edit_card_field("context", "Исходный текст", "Сделай короче", "другой")
    assert result["error"]["code"] == "invalid_input"


def test_solution_coach_uses_grounded_ai_response(monkeypatch):
    captured = {}

    def fake_ask(system_prompt, payload, response_type, reasoning_effort=None):
        captured.update(payload)
        assert response_type is ai.CoachResponse
        assert reasoning_effort == "high"
        return {"text": "Начните с проверки критериев вместе с бизнесом."}

    monkeypatch.setattr(ai, "_ask_model", fake_ask)
    result = ai.coach_solution(
        {"title": "Прототип", "success_criteria": "Пять успешных тестов"},
        "С чего начать?",
    )

    assert result["source"] == "ai"
    assert captured["question"] == "С чего начать?"
    assert captured["task"]["success_criteria"] == "Пять успешных тестов"


def test_solution_coach_has_safe_fallback(monkeypatch):
    monkeypatch.setattr(ai, "_ask_model", lambda *_args, **_kwargs: None)
    result = ai.coach_solution({"title": "Прототип"}, "Сделай всё за нас")
    assert result["source"] == "fallback"
    assert "не выполню" in result["text"]
