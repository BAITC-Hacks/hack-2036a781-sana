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
