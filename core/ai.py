"""OpenAI-backed clarification with deterministic, fact-preserving fallback."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from core.prompts import ANALYZE_SYSTEM_PROMPT, BUILD_CARD_SYSTEM_PROMPT
from core.rating import METRICS, calculate_rating, missing_fields


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

MAX_DRAFT_LENGTH = 4000
MAX_ANSWER_LENGTH = 2000
CARD_FIELDS = (
    "title",
    "context",
    "need",
    "users",
    "data_materials",
    "constraints",
    "expected_result",
    "success_criteria",
    "contact",
    "interaction_format",
)
VALID_KEYS = {metric[0] for metric in METRICS}

FALLBACK_QUESTIONS = {
    "context_need": "Что происходит сейчас и что именно вы хотите изменить?",
    "data_materials": "Какие данные, примеры или материалы вы готовы предоставить?",
    "expected_result": "Какой конкретный результат вы ожидаете от студенческой команды?",
    "success_criteria": "По каким измеримым признакам вы поймёте, что результат подходит?",
    "constraints": "Какие сроки, технологии, доступы или другие ограничения нужно учесть?",
    "users": "Кто будет пользоваться предлагаемым решением?",
    "business_link": "Кто будет контактным лицом и как команда сможет получать обратную связь?",
}

FALLBACK_QUESTIONS_I18N = {
    "kk": {
        "context_need": "Қазір не болып жатыр және нақты нені өзгерткіңіз келеді?",
        "data_materials": "Қандай деректерді, мысалдарды немесе материалдарды бере аласыз?",
        "expected_result": "Студенттер командасынан қандай нақты нәтиже күтесіз?",
        "success_criteria": "Нәтиженің сәйкес екенін қандай өлшенетін белгілерден білесіз?",
        "constraints": "Қандай мерзім, технология, қолжетімділік немесе басқа шектеу бар?",
        "users": "Ұсынылған шешімді кім қолданады?",
        "business_link": "Байланыс тұлғасы кім және команда кері байланысты қалай алады?",
    },
    "en": {
        "context_need": "What is happening now, and what exactly would you like to change?",
        "data_materials": "What data, examples, or materials can you provide?",
        "expected_result": "What specific result do you expect from the student team?",
        "success_criteria": "Which measurable signs will show that the result meets your needs?",
        "constraints": "Which deadlines, technologies, access requirements, or other constraints apply?",
        "users": "Who will use the proposed solution?",
        "business_link": "Who is the contact person, and how can the team receive feedback?",
    },
}
LANGUAGE_NAMES = {"ru": "Russian", "kk": "Kazakh", "en": "English"}


def _error(message: str) -> dict:
    return {"error": {"code": "invalid_input", "message": message}}


def _valid_draft(draft: Any) -> bool:
    return isinstance(draft, str) and bool(draft.strip()) and len(draft) <= MAX_DRAFT_LENGTH


def _client() -> OpenAI | None:
    if os.getenv("AI_MODE", "").strip().casefold() == "fallback":
        return None
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
        timeout = min(max(timeout, 1.0), 60.0)
        return OpenAI(api_key=api_key, timeout=timeout, max_retries=0)
    except (TypeError, ValueError):
        return None


def _ask_model(system_prompt: str, payload: dict) -> dict | None:
    client = _client()
    if client is None:
        return None
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
        )
        content = response.choices[0].message.content
        if not isinstance(content, str):
            return None
        result = json.loads(content)
        return result if isinstance(result, dict) else None
    except Exception:
        # Network, provider, and malformed-response errors all use the explicit fallback.
        return None


def _baseline_missing(draft: str) -> list[str]:
    card = {field: "" for field in CARD_FIELDS}
    card["context"] = draft
    return missing_fields(card)


def _fallback_questions(draft: str, language: str = "ru") -> dict:
    missing = _baseline_missing(draft)
    questions_by_key = FALLBACK_QUESTIONS_I18N.get(language, FALLBACK_QUESTIONS)
    ordered_keys = [metric[0] for metric in METRICS if metric[0] in missing]
    questions = [
        {"key": key, "question": questions_by_key[key]}
        for key in ordered_keys[:5]
    ]
    if len(questions) < 3:
        for key in ("data_materials", "expected_result", "success_criteria"):
            if all(item["key"] != key for item in questions):
                questions.append({"key": key, "question": questions_by_key[key]})
            if len(questions) == 3:
                break
    return {"questions": questions, "missing": missing, "source": "fallback"}


def analyze_draft(draft: str, industry: str = "", language: str = "ru") -> dict:
    language = language if language in LANGUAGE_NAMES else "ru"
    if not _valid_draft(draft):
        return _error(f"Введите описание длиной до {MAX_DRAFT_LENGTH} символов.")
    if not isinstance(industry, str) or len(industry) > 80:
        return _error("Тема должна быть текстом длиной до 80 символов.")

    fallback = _fallback_questions(draft.strip(), language)
    result = _ask_model(
        ANALYZE_SYSTEM_PROMPT + f"\nWrite all generated questions in {LANGUAGE_NAMES[language]}.",
        {"draft": draft.strip(), "industry": industry.strip(), "language": language},
    )
    if result is None:
        return fallback

    raw_questions = result.get("questions")
    questions = []
    if isinstance(raw_questions, list):
        for item in raw_questions:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            question = item.get("question")
            if key in VALID_KEYS and isinstance(question, str) and question.strip():
                if all(existing["key"] != key for existing in questions):
                    questions.append({"key": key, "question": question.strip()[:300]})
            if len(questions) == 5:
                break

    if len(questions) < 3:
        return fallback
    return {
        "questions": questions,
        "missing": fallback["missing"],
        "source": "ai",
    }


def _normalize_answers(answers: Any) -> list[dict] | None:
    if not isinstance(answers, list) or len(answers) > 20:
        return None
    normalized = []
    for answer in answers:
        if not isinstance(answer, dict):
            return None
        key = answer.get("key")
        value = answer.get("answer", "")
        if key not in VALID_KEYS:
            return None
        if not isinstance(value, str) or len(value) > MAX_ANSWER_LENGTH:
            return None
        if value.strip():
            normalized.append({"key": key, "answer": value.strip()})
    return normalized


def _fallback_card(draft: str, industry: str, answers: list[dict]) -> dict:
    first_line = next((line.strip() for line in draft.splitlines() if line.strip()), "")
    card = {field: "" for field in CARD_FIELDS}
    card["title"] = first_line[:120]
    card["context"] = draft.strip()
    card["industry"] = industry.strip()

    answer_fields = {
        "context_need": "need",
        "data_materials": "data_materials",
        "expected_result": "expected_result",
        "success_criteria": "success_criteria",
        "constraints": "constraints",
        "users": "users",
        "business_link": "contact",
    }
    for answer in answers:
        field = answer_fields.get(answer["key"])
        if field and not card[field]:
            card[field] = answer["answer"]
    card["status"] = "draft"
    card["rating"] = calculate_rating(card)
    return card


def _verified_fields(result: dict, source_text: str) -> dict:
    raw_fields = result.get("fields")
    if not isinstance(raw_fields, dict):
        return {}
    verified = {}
    for field in CARD_FIELDS:
        item = raw_fields.get(field)
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence")
        if isinstance(evidence, str) and evidence.strip() and evidence in source_text:
            verified[field] = evidence.strip()
    return verified


def build_card(draft: str, answers: list[dict], language: str = "ru") -> dict:
    language = language if language in LANGUAGE_NAMES else "ru"
    if not _valid_draft(draft):
        return _error(f"Введите описание длиной до {MAX_DRAFT_LENGTH} символов.")
    normalized_answers = _normalize_answers(answers)
    if normalized_answers is None:
        return _error("Ответы должны быть списком корректных полей и не длиннее 2000 символов.")

    industry = ""
    fallback = _fallback_card(draft.strip(), industry, normalized_answers)
    answer_lines = [
        f"{answer['key']}: {answer['answer']}" for answer in normalized_answers
    ]
    source_text = draft.strip() + "\n" + "\n".join(answer_lines)
    result = _ask_model(
        BUILD_CARD_SYSTEM_PROMPT + f"\nUse {LANGUAGE_NAMES[language]} for any generated text. Never translate or invent source facts.",
        {"draft": draft.strip(), "answers": normalized_answers, "language": language},
    )
    if result is None:
        return {"card": fallback, "source": "fallback"}

    verified = _verified_fields(result, source_text)
    card = dict(fallback)
    for field, evidence in verified.items():
        if field in {"title", "context"} and field == "title":
            continue
        card[field] = evidence
    card["industry"] = industry
    card["status"] = "draft"
    card["rating"] = calculate_rating(card)
    return {"card": card, "source": "ai"}
