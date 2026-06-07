import logging

from openai import OpenAI

from ai_manager import OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT
from seasonal_manager import get_seasonal_system_prompt


logger = logging.getLogger(__name__)

TOURS = {
    "samet": "Ко Самет",
    "chang": "Ко Чанг",
    "bangkok": "Бангкок",
    "nongnooch": "Нонг Нуч",
    "khao_kheow": "Кхао Кхео",
}


def normalize_tour_key(tour_key):
    return tour_key.replace("-", "_").lower()


def generate_product_card(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour_name = TOURS.get(normalized_tour_key)
    if not tour_name:
        logger.error("Unknown tour key: %s", tour_key)
        return None

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not configured")
        return None

    prompt = (
        f"Сгенерируй карточку экскурсии для ВК: {tour_name}.\n"
        "Строго используй структуру:\n"
        "заголовок\n"
        "эмоциональный крючок\n"
        "что включено\n"
        "длительность\n"
        "для кого\n"
        "выезд\n"
        "отправление\n"
        "цена от\n"
        "CTA\n"
        "хэштеги\n\n"
        "Пиши от лица Максима Орлова. Текст должен быть готов к публикации в ВК."
    )

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=get_seasonal_system_prompt(SYSTEM_PROMPT),
            input=prompt,
        )
        return response.output_text.strip()
    except Exception:
        logger.exception("OpenAI product card generation failed")
        return None
