from core.rating import METRICS, calculate_rating, get_level


def full_card():
    return {
        "context": "Преподаватели проверяют работы вручную каждый день.",
        "need": "Нужно сократить время проверки без автоматической оценки.",
        "data_materials": "Есть обезличенные примеры работ и утверждённая рубрика.",
        "expected_result": "Прототип выдаёт черновик пояснения для учителя.",
        "success_criteria": "Учитель подтверждает полезность в восьми случаях из десяти.",
        "constraints": "Не использовать персональные данные учеников и оценки.",
        "users": "Преподаватели и методист онлайн-школы.",
        "contact": "Связь через ответственного методиста учебной программы.",
        "interaction_format": "Еженедельная встреча для проверки прототипа и обратной связи.",
    }


def test_full_card_scores_100_and_priority():
    result = calculate_rating(full_card())
    assert result["score"] == 100
    assert result["level"] == "priority"
    assert result["missing"] == []
    assert len(result["breakdown"]) == 7


def test_empty_or_invalid_card_scores_zero():
    for card in ({}, None, "text", []):
        result = calculate_rating(card)
        assert result["score"] == 0
        assert result["level"] == "draft"
        assert len(result["missing"]) == 7


def test_one_of_two_fields_earns_half():
    result = calculate_rating({"context": "Преподаватели проверяют задания вручную каждый день."})
    assert result["breakdown"][0]["earned"] == 10
    assert result["breakdown"][0]["filled"] is False


def test_short_text_does_not_count():
    result = calculate_rating({"data_materials": "три"})
    assert result["breakdown"][1]["earned"] == 0


def test_levels_cover_case_boundaries():
    expected = {
        39: "draft",
        40: "working",
        69: "working",
        70: "ready",
        89: "ready",
        90: "priority",
        100: "priority",
    }
    assert {score: get_level(score) for score in expected} == expected


def test_breakdown_weights_sum_to_100_and_tips_are_sorted():
    result = calculate_rating({})
    assert sum(item["max"] for item in result["breakdown"]) == 100
    weights_by_key = {key: weight for key, _label, weight, _fields, _tip in METRICS}
    tip_weights = [
        next(
            weights_by_key[item["key"]]
            for item in result["breakdown"]
            if f"+{weights_by_key[item['key']]} баллов" in tip
        )
        for tip in result["tips"]
    ]
    assert tip_weights == sorted(tip_weights, reverse=True)


def test_adding_fields_never_decreases_score():
    card = full_card()
    fields = list(card)
    partial = {}
    previous = 0
    for field in fields:
        partial[field] = card[field]
        score = calculate_rating(partial)["score"]
        assert score >= previous
        previous = score

