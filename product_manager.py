import logging
import re

from openai import OpenAI

from ai_manager import OPENAI_API_KEY, OPENAI_MODEL, SYSTEM_PROMPT
from seasonal_manager import get_seasonal_system_prompt
from tour_catalog import TOUR_CATALOG, format_tour_data, get_public_tour, normalize_tour_key


logger = logging.getLogger(__name__)

AVAILABLE_TOUR_KEYS = ", ".join(TOUR_CATALOG.keys())
PHOTO_SLOT_FALLBACKS = ["обложка", "фото 1", "фото 2", "фото 3", "фото 4"]


def format_route_block(tour):
    route = tour.get("route") or []
    if not route:
        return ""

    if isinstance(route, dict):
        lines = ["🧭 Маршрут:"]
        stops = route.get("stops") or []
        boat_view = route.get("boat_view") or []
        if stops:
            lines.extend(["Остановки:", *[f"- {item}" for item in stops]])
        if boat_view:
            lines.extend(["Обзор с лодки:", *[f"- {item}" for item in boat_view]])
        return "\n".join(lines)

    return "\n".join(["🧭 Маршрут:", *[f"- {item}" for item in route]])


def add_route_before_included(card_text, tour):
    route_block = format_route_block(tour)
    if not route_block:
        return card_text.strip()

    included_match = re.search(r"(?im)^.*что\s+включено.*$", card_text)
    if not included_match:
        return f"{card_text.strip()}\n\n{route_block}"

    return (
        f"{card_text[:included_match.start()].rstrip()}\n\n"
        f"{route_block}\n\n"
        f"{card_text[included_match.start():].lstrip()}"
    ).strip()


def get_missing_photo_requirements(tour):
    photos = tour.get("photos") or {}
    required_photos = photos.get("required") or []
    gallery = photos.get("gallery") or []
    missing_slots = []

    if not photos.get("cover"):
        missing_slots.append(0)

    for gallery_index in range(4):
        if gallery_index >= len(gallery) or not gallery[gallery_index]:
            missing_slots.append(gallery_index + 1)

    photo_requirements = required_photos or PHOTO_SLOT_FALLBACKS
    return [
        photo_requirements[slot_index]
        for slot_index in missing_slots
        if slot_index < len(photo_requirements)
    ][:5]


def add_missing_photos_block(card_text, tour):
    missing_photos = get_missing_photo_requirements(tour)
    if not missing_photos:
        return card_text.strip()

    photos_block = "\n".join(["📷 Нужны фото:", *[f"- {item}" for item in missing_photos]])
    return f"{card_text.strip()}\n\n{photos_block}"


def finalize_product_card(card_text, tour):
    card_with_route = add_route_before_included(card_text, tour)
    return add_missing_photos_block(card_with_route, tour)


def generate_product_card(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour = get_public_tour(normalized_tour_key)
    if not tour:
        logger.error("Unknown tour key: %s", tour_key)
        return None

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY is not configured")
        return None

    prompt = (
        f"Сгенерируй карточку экскурсии для ВК: {tour['title']}.\n"
        "Используй только данные из каталога ниже. Не выдумывай цены, отели или условия.\n"
        "Показывай только клиентские цены из публичного каталога. Не упоминай "
        "внутренние цены, маржу или условия партнёров.\n"
        "Если в данных есть маршрут, не выводи его сам: маршрут будет добавлен системой отдельно.\n"
        "Не пиши, что на всех 9 островах есть высадка.\n"
        f"Данные тура:\n{format_tour_data(tour, include_route=False)}\n\n"
        "Строго используй структуру:\n"
        "заголовок\n"
        "эмоциональный крючок\n"
        "что включено\n"
        "⏱ Длительность: используй только поле duration\n"
        "🚐 Время в пути: используй только поле travel_time\n"
        "для кого\n"
        "📍 Отправление: используй поле departure или departure_time. "
        "Если их нет, пиши \"уточняется при бронировании\".\n"
        "цена взрослый/ребёнок\n"
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
        return finalize_product_card(response.output_text, tour)
    except Exception:
        logger.exception("OpenAI product card generation failed")
        return None
