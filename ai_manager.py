import logging
import os
import re

from openai import OpenAI

from seasonal_manager import get_seasonal_system_prompt
from tour_catalog import get_samet_catalog_context


logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """Ты Максим Орлов, русскоязычный гид и консультант по отдыху в Паттайе.
Помогаешь туристам подобрать острова, экскурсии, море и формат отдыха.
Отвечай дружелюбно, уверенно и по делу.
Задавай уточняющие вопросы, если не хватает данных: количество человек, даты, интересы, бюджет и формат отдыха.
Пиши коротко, живым человеческим языком, без канцелярита."""


def is_samet_question(user_message, history=None):
    texts = [user_message]
    if history:
        texts.extend(message.get("content", "") for message in history)

    combined_text = " ".join(texts).lower()
    return bool(re.search(r"\b(самет|samet|samed|ко самет|koh samet)\b", combined_text))


def add_catalog_context(messages):
    return [
        {
            "role": "developer",
            "content": (
                "Если клиент спрашивает про Самет, используй данные каталога ниже "
                "как источник правды, не выдумывай цены или условия и показывай "
                "только клиентские цены из публичного каталога. Не упоминай "
                "внутренние цены, маржу или условия партнёров.\n\n"
                f"{get_samet_catalog_context()}"
            ),
        },
        *messages,
    ]


def generate_reply(user_message, history=None):
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not configured")
        return None

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        messages = history or [{"role": "user", "content": user_message}]
        if is_samet_question(user_message, history=history):
            messages = add_catalog_context(messages)

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=get_seasonal_system_prompt(SYSTEM_PROMPT),
            input=messages,
        )
        return response.output_text.strip()
    except Exception:
        logger.exception("OpenAI reply generation failed")
        return None
