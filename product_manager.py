import logging

from openai import OpenAI

from ai_manager import OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT
from seasonal_manager import get_seasonal_system_prompt


logger = logging.getLogger(__name__)

TOURS = {
    "samet_1d": {
        "name": "Остров Самет 1 день",
        "details": """Остров Самет 1 день.
Включено:
трансфер от отеля в Паттайе и обратно,
скоростной катер до острова и обратно,
билет в национальный парк,
лежаки и зонтики на пляже Ао Пай,
легкий обед,
сопровождение русского гида.
Время в пути:
около 1 часа на минивене и 15 минут на скоростном катере.""",
    },
    "samet_2d": {
        "name": "Остров Самет 2 дня",
        "details": """Остров Самет 2 дня.
Включено:
трансфер от отеля в Паттайе и обратно,
скоростной катер до острова и обратно,
билет в национальный парк,
проживание в отелях на выбор:
Silver Sand Hotel,
Tok’s Little Hut,
Sea Breeze.
Указать, что формат подходит для спокойного отдыха с ночёвкой.""",
    },
    "samet_transfer": {
        "name": "Трансфер на Самет",
        "details": """Трансфер на Самет.
Включено:
трансфер от отеля в Паттайе и обратно,
скоростной катер до острова Самет,
билет в национальный парк.
Указать, что программа подходит тем, кто едет на остров на несколько дней и хочет сам выбрать отель.""",
    },
    "chang": {"name": "Ко Чанг", "details": ""},
    "bangkok": {"name": "Бангкок", "details": ""},
    "nongnooch": {"name": "Нонг Нуч", "details": ""},
    "khao_kheow": {"name": "Кхао Кхео", "details": ""},
}

AVAILABLE_TOUR_KEYS = ", ".join(TOURS.keys())


def normalize_tour_key(tour_key):
    return tour_key.replace("-", "_").lower()


def generate_product_card(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour = TOURS.get(normalized_tour_key)
    if not tour:
        logger.error("Unknown tour key: %s", tour_key)
        return None

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not configured")
        return None

    prompt = (
        f"Сгенерируй карточку экскурсии для ВК: {tour['name']}.\n"
        f"Данные тура:\n{tour['details'] or 'Используй знания Максима Орлова по этому направлению.'}\n\n"
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
