import logging

from openai import OpenAI

from ai_manager import OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT
from seasonal_manager import get_seasonal_system_prompt
from tour_catalog import TOUR_CATALOG, format_tour_data, get_tour, normalize_tour_key


logger = logging.getLogger(__name__)

AVAILABLE_TOUR_KEYS = ", ".join(TOUR_CATALOG.keys())


def generate_product_card(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour = get_tour(normalized_tour_key)
    if not tour:
        logger.error("Unknown tour key: %s", tour_key)
        return None

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not configured")
        return None

    prompt = (
        f"Сгенерируй карточку экскурсии для ВК: {tour['title']}.\n"
        "Используй только данные из каталога ниже. Не выдумывай цены, отели или условия.\n"
        f"Данные тура:\n{format_tour_data(tour)}\n\n"
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
