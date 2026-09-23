"""OpenAI-backed clarification with deterministic, fact-preserving fallback."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from core.prompts import ANALYZE_SYSTEM_PROMPT, BUILD_CARD_SYSTEM_PROMPT
from core.rating import METRICS, calculate_rating, missing_fields


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
LOGGER = logging.getLogger(__name__)

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
DEFAULT_OPENAI_MODEL = "gpt-6-astra"
VALID_REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "max"}

QuestionKey = Literal[
    "context_need",
    "data_materials",
    "expected_result",
    "success_criteria",
    "constraints",
    "users",
    "business_link",
]


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: QuestionKey
    question: str = Field(min_length=3, max_length=300)
    suggestions: list[str] = Field(min_length=3, max_length=3)


class AnalyzeModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[ClarificationQuestion] = Field(min_length=3, max_length=5)


class EvidenceField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: str


class CardEvidenceFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: EvidenceField
    context: EvidenceField
    need: EvidenceField
    users: EvidenceField
    data_materials: EvidenceField
    constraints: EvidenceField
    expected_result: EvidenceField
    success_criteria: EvidenceField
    contact: EvidenceField
    interaction_format: EvidenceField


class BuildCardModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: CardEvidenceFields


ModelResponse = TypeVar("ModelResponse", bound=BaseModel)

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
FALLBACK_SUGGESTIONS_I18N = {
    "ru": {
        "context_need": [
            "Сейчас процесс выполняется вручную и занимает слишком много времени.",
            "Используем несколько несвязанных инструментов, поэтому возникают ошибки.",
            "Текущий процесс ещё нужно изучить вместе с будущими пользователями.",
        ],
        "data_materials": [
            "Есть обезличенные примеры и описание текущего процесса.",
            "Есть только несколько примеров, дополнительные данные соберём позже.",
            "Готовых материалов пока нет, их нужно создать в рамках проекта.",
        ],
        "expected_result": [
            "Нужен работающий прототип, который можно показать пользователям.",
            "Нужны исследование проблемы и проверенная концепция решения.",
            "Нужны рекомендации, план внедрения и демонстрационный макет.",
        ],
        "success_criteria": [
            "Пользователи выполняют задачу быстрее и допускают меньше ошибок.",
            "Не менее пяти пользователей успешно проверяют прототип.",
            "Заказчик принимает демонстрацию по заранее согласованному сценарию.",
        ],
        "constraints": [
            "Срок — четыре недели, можно использовать только обезличенные данные.",
            "Решение должно работать в браузере без платных сервисов.",
            "Жёстких ограничений пока нет, их согласуем после первого прототипа.",
        ],
        "users": [
            "Основные пользователи — преподаватели и методисты.",
            "Решением будут пользоваться студенты и преподаватели.",
            "Сначала прототип проверит небольшая пилотная группа.",
        ],
        "business_link": [
            "Контактное лицо будет отвечать в чате и проводить встречу раз в неделю.",
            "Команда получит письменную обратную связь после каждого этапа.",
            "Доступна одна установочная встреча и финальная демонстрация.",
        ],
    },
    "en": {
        "context_need": ["The process is manual and takes too long.", "Several disconnected tools cause mistakes.", "We still need to study the current process with users."],
        "data_materials": ["We have anonymized examples and a process description.", "We only have a few examples and will collect more later.", "No materials are ready yet; the project should create them."],
        "expected_result": ["We need a working prototype for user testing.", "We need problem research and a validated solution concept.", "We need recommendations, an implementation plan, and a demo mockup."],
        "success_criteria": ["Users complete the task faster with fewer errors.", "At least five users successfully test the prototype.", "The customer accepts the demo against an agreed scenario."],
        "constraints": ["The deadline is four weeks and only anonymized data may be used.", "The solution must run in a browser without paid services.", "There are no strict constraints yet; we will agree them after the first prototype."],
        "users": ["The main users are teachers and methodologists.", "Students and teachers will use the solution.", "A small pilot group will test the first version."],
        "business_link": ["A contact person will answer in chat and meet weekly.", "The team will receive written feedback after each stage.", "One kickoff meeting and one final demo are available."],
    },
    "kk": {
        "context_need": ["Қазір жұмыс қолмен орындалады және көп уақыт алады.", "Бірнеше байланыспаған құрал қателерге әкеледі.", "Қазіргі үдерісті пайдаланушылармен бірге әлі зерттеу керек."],
        "data_materials": ["Иесіздендірілген мысалдар мен үдеріс сипаттамасы бар.", "Әзірге бірнеше мысал ғана бар, қалғанын кейін жинаймыз.", "Дайын материал жоқ, оны жоба аясында жасау керек."],
        "expected_result": ["Пайдаланушыларға көрсетуге болатын жұмыс прототипі керек.", "Мәселені зерттеу және тексерілген шешім тұжырымдамасы керек.", "Ұсынымдар, енгізу жоспары және демо-макет керек."],
        "success_criteria": ["Пайдаланушылар жұмысты жылдам әрі аз қатемен орындайды.", "Кемінде бес пайдаланушы прототипті сәтті тексереді.", "Тапсырыс беруші келісілген сценарий бойынша демонстрацияны қабылдайды."],
        "constraints": ["Мерзім — төрт апта, тек иесіздендірілген деректер қолданылады.", "Шешім ақылы сервистерсіз браузерде жұмыс істеуі керек.", "Қатаң шектеулер әзірге жоқ, оларды алғашқы прототиптен кейін келісеміз."],
        "users": ["Негізгі пайдаланушылар — оқытушылар мен әдіскерлер.", "Шешімді студенттер мен оқытушылар қолданады.", "Алғашқы нұсқаны шағын пилоттық топ тексереді."],
        "business_link": ["Байланыс тұлғасы чатта жауап беріп, апта сайын кездесу өткізеді.", "Команда әр кезеңнен кейін жазбаша кері байланыс алады.", "Бір бастапқы кездесу және бір финалдық көрсетілім қолжетімді."],
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
        timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))
        timeout = min(max(timeout, 1.0), 180.0)
        return OpenAI(api_key=api_key, timeout=timeout, max_retries=0)
    except (TypeError, ValueError):
        return None


def _reasoning_effort() -> str:
    effort = os.getenv("OPENAI_REASONING_EFFORT", "max").strip().casefold()
    return effort if effort in VALID_REASONING_EFFORTS else "max"


def _max_output_tokens() -> int:
    try:
        value = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "6000"))
    except ValueError:
        return 6000
    return min(max(value, 512), 16000)


def _ask_model(
    system_prompt: str,
    payload: dict,
    response_type: type[ModelResponse],
    reasoning_effort: str | None = None,
) -> dict | None:
    client = _client()
    if client is None:
        return None
    try:
        response = client.responses.parse(
            model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
            or DEFAULT_OPENAI_MODEL,
            reasoning={
                "effort": reasoning_effort
                if reasoning_effort in VALID_REASONING_EFFORTS
                else _reasoning_effort()
            },
            max_output_tokens=_max_output_tokens(),
            store=False,
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            text_format=response_type,
        )
        parsed = response.output_parsed
        if not isinstance(parsed, response_type):
            return None
        return parsed.model_dump()
    except Exception:
        # Network, provider, refusal, and malformed-response errors use the safe fallback.
        LOGGER.warning("OpenAI structured response failed; using fallback.", exc_info=True)
        return None


def _baseline_missing(draft: str) -> list[str]:
    card = {field: "" for field in CARD_FIELDS}
    card["context"] = draft
    return missing_fields(card)


def _fallback_questions(draft: str, language: str = "ru") -> dict:
    missing = _baseline_missing(draft)
    questions_by_key = FALLBACK_QUESTIONS_I18N.get(language, FALLBACK_QUESTIONS)
    suggestions_by_key = FALLBACK_SUGGESTIONS_I18N.get(
        language, FALLBACK_SUGGESTIONS_I18N["ru"]
    )
    ordered_keys = [metric[0] for metric in METRICS if metric[0] in missing]
    questions = [
        {
            "key": key,
            "question": questions_by_key[key],
            "suggestions": suggestions_by_key[key],
        }
        for key in ordered_keys[:5]
    ]
    if len(questions) < 3:
        for key in ("data_materials", "expected_result", "success_criteria"):
            if all(item["key"] != key for item in questions):
                questions.append(
                    {
                        "key": key,
                        "question": questions_by_key[key],
                        "suggestions": suggestions_by_key[key],
                    }
                )
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
        AnalyzeModelResponse,
        "high",
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
            suggestions = item.get("suggestions")
            clean_suggestions = []
            if isinstance(suggestions, list):
                for suggestion in suggestions:
                    if isinstance(suggestion, str) and suggestion.strip():
                        normalized = suggestion.strip()[:300]
                        if normalized not in clean_suggestions:
                            clean_suggestions.append(normalized)
            if (
                key in VALID_KEYS
                and isinstance(question, str)
                and question.strip()
                and len(clean_suggestions) == 3
            ):
                if all(existing["key"] != key for existing in questions):
                    questions.append(
                        {
                            "key": key,
                            "question": question.strip()[:300],
                            "suggestions": clean_suggestions,
                        }
                    )
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
        BuildCardModelResponse,
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
