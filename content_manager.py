import logging

from openai import OpenAI

from ai_manager import OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT
from seasonal_manager import get_seasonal_system_prompt


logger = logging.getLogger(__name__)


def generate_post(topic):
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not configured")
        return None

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=get_seasonal_system_prompt(SYSTEM_PROMPT),
            input=topic,
        )
        return response.output_text.strip()
    except Exception:
        logger.exception("OpenAI post generation failed")
        return None


def generate_expert_post():
    return generate_post(
        "Напиши экспертный пост для публикации ВК от лица Максима Орлова. "
        "Тема: как выбрать экскурсию или острова в Паттайе без разочарований. "
        "Стиль: уверенно, полезно, с конкретикой, без воды. В конце мягкий призыв написать в сообщения."
    )


def generate_sales_post():
    return generate_post(
        "Напиши продающий пост для публикации ВК от лица Максима Орлова. "
        "Цель: получить заявки на подбор экскурсий, островов и морского отдыха в Паттайе. "
        "Стиль: дружелюбно, убедительно, без агрессивных продаж. В конце призыв написать даты и количество человек."
    )


def generate_story_post():
    return generate_post(
        "Напиши сторителлинг-пост для публикации ВК от лица Максима Орлова. "
        "Тема: туристы не знали, куда поехать в Паттайе, а после короткого уточнения получили удачный маршрут. "
        "Стиль: живой рассказ, человеческий тон, с выводом и мягким призывом написать в сообщения."
    )
