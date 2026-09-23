"""Deterministic task readiness scoring."""

from __future__ import annotations

from typing import Any


MIN_FIELD_LENGTH = 15

METRICS = (
    ("context_need", "Контекст и потребность", 20, ("context", "need"), "контекст и потребность"),
    ("data_materials", "Данные и материалы", 20, ("data_materials",), "доступные данные и материалы"),
    ("expected_result", "Ожидаемый результат", 15, ("expected_result",), "конкретный ожидаемый результат"),
    ("success_criteria", "Критерии успеха", 15, ("success_criteria",), "измеримые критерии успеха"),
    ("constraints", "Ограничения", 10, ("constraints",), "сроки, технологии и другие ограничения"),
    ("users", "Пользователи", 10, ("users",), "пользователей решения"),
    ("business_link", "Связь с бизнесом", 10, ("contact", "interaction_format"), "контакт и формат взаимодействия"),
)


def get_level(score: int) -> str:
    """Map a numeric score to the case readiness band."""
    try:
        value = int(score)
    except (TypeError, ValueError):
        value = 0
    if value < 40:
        return "draft"
    if value < 70:
        return "working"
    if value < 90:
        return "ready"
    return "priority"


def _is_filled(value: Any) -> bool:
    return isinstance(value, str) and len(value.strip()) >= MIN_FIELD_LENGTH


def missing_fields(card: dict | None) -> list[str]:
    """Return metric keys that still have at least one missing field."""
    if not isinstance(card, dict):
        card = {}
    return [
        key
        for key, _label, _weight, fields, _tip in METRICS
        if not all(_is_filled(card.get(field)) for field in fields)
    ]


def calculate_rating(card: dict | None) -> dict:
    """Calculate a transparent 0-100 score without I/O or side effects."""
    if not isinstance(card, dict):
        card = {}

    score = 0
    breakdown = []
    missing = []
    tips = []

    for key, label, weight, fields, tip_text in METRICS:
        filled_fields = sum(_is_filled(card.get(field)) for field in fields)
        complete = filled_fields == len(fields)
        if complete:
            earned = weight
        elif len(fields) == 2 and filled_fields == 1:
            earned = weight // 2
        else:
            earned = 0

        score += earned
        breakdown.append(
            {
                "key": key,
                "label": label,
                "earned": earned,
                "max": weight,
                "filled": complete,
            }
        )
        if not complete:
            missing.append(key)
            points_to_add = weight - earned
            tips.append(
                (weight, f"Добавьте {tip_text} — это +{points_to_add} баллов")
            )

    tips.sort(key=lambda item: item[0], reverse=True)
    return {
        "score": score,
        "level": get_level(score),
        "breakdown": breakdown,
        "missing": missing,
        "tips": [tip for _weight, tip in tips],
    }
