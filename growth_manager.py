from pathlib import Path

from database import get_lead_status_counts
from tour_catalog import TOUR_CATALOG


PHOTO_SLOT_FALLBACKS = ["обложка", "фото 1", "фото 2", "фото 3", "фото 4"]
PHOTO_FILENAMES = ["cover.jpg", "gallery_1.jpg", "gallery_2.jpg", "gallery_3.jpg", "gallery_4.jpg"]
STATIC_TOURS_DIR = Path(__file__).resolve().parent / "static" / "tours"


def get_tour_keys_by_status(status):
    return [
        tour_key
        for tour_key, tour in TOUR_CATALOG.items()
        if tour.get("status") == status
    ]


def get_static_photo_paths(tour_key):
    tour_dir = STATIC_TOURS_DIR / tour_key
    return [tour_dir / filename for filename in PHOTO_FILENAMES]


def get_photo_slot_values(tour_key, tour):
    photos = tour.get("photos") or {}
    gallery = photos.get("gallery") or []
    catalog_values = [
        photos.get("cover"),
        *[
            gallery[gallery_index]
            if gallery_index < len(gallery)
            else ""
            for gallery_index in range(4)
        ],
    ]

    return [
        catalog_value or (str(static_path) if static_path.exists() else "")
        for catalog_value, static_path in zip(catalog_values, get_static_photo_paths(tour_key))
    ]


def is_missing_photos(tour, tour_key=None):
    if tour_key is None:
        photos = tour.get("photos") or {}
        gallery = photos.get("gallery") or []
        return not photos.get("cover") or any(
            gallery_index >= len(gallery) or not gallery[gallery_index]
            for gallery_index in range(4)
        )

    photo_slot_values = get_photo_slot_values(tour_key, tour)
    return any(not photo_value for photo_value in photo_slot_values)


def get_missing_photo_requirements(tour, tour_key=None):
    if not is_missing_photos(tour, tour_key):
        return []

    photos = tour.get("photos") or {}
    required_photos = photos.get("required") or []
    photo_requirements = required_photos or PHOTO_SLOT_FALLBACKS

    if tour_key is not None:
        photo_slot_values = get_photo_slot_values(tour_key, tour)
        return [
            photo_requirements[slot_index]
            for slot_index, photo_value in enumerate(photo_slot_values)
            if not photo_value and slot_index < len(photo_requirements)
        ][:5]

    gallery = photos.get("gallery") or []
    catalog_values = [
        photos.get("cover"),
        *[
            gallery[gallery_index]
            if gallery_index < len(gallery)
            else ""
            for gallery_index in range(4)
        ],
    ]
    return [
        photo_requirements[slot_index]
        for slot_index, photo_value in enumerate(catalog_values)
        if not photo_value and slot_index < len(photo_requirements)
    ][:5]


def is_missing_price(tour):
    return not (tour.get("price_adult") or tour.get("price_from"))


def format_key_list(title, keys):
    if not keys:
        return f"{title}\nнет"

    return "\n".join([title, *[f"- {key}" for key in keys]])


def format_missing_photos(tours_without_photos):
    if not tours_without_photos:
        return "Туры без фото:\nнет"

    lines = ["Туры без фото:"]
    for tour_key, missing_photos in tours_without_photos.items():
        lines.append(f"- {tour_key}:")
        lines.extend(f"  - {photo}" for photo in missing_photos)
    return "\n".join(lines)


def format_lead_stage_counts():
    counts = get_lead_status_counts()
    lines = ["Лиды по стадиям:"]
    for stage in ("new", "qualified", "offer_sent", "booked", "lost"):
        lines.append(f"- {stage}: {counts.get(stage, 0)}")
    return "\n".join(lines)


def build_recommendations(active_tours, draft_tours, tours_without_photos, tours_without_price, lead_counts):
    recommendations = []

    if draft_tours:
        recommendations.append("Довести draft-туры до полного описания, цен и фото.")

    if tours_without_photos:
        recommendations.append("Добавить cover и 4 gallery-фото для активных товаров.")

    if tours_without_price:
        recommendations.append("Проверить цены или price_from у товаров без цены.")

    if lead_counts.get("qualified", 0) > 0:
        recommendations.append("Подготовить предложения для qualified-лидов.")

    if lead_counts.get("offer_sent", 0) > 0:
        recommendations.append("Дожать лиды в offer_sent: уточнить решение и предложить бронирование.")

    if not active_tours:
        recommendations.append("Добавить активные товары для публикации и экспорта.")

    if not recommendations:
        recommendations.append("Критичных проблем не найдено. Можно обновить фото и проверить актуальность цен.")

    return recommendations


def generate_admin_audit():
    active_tours = get_tour_keys_by_status("active")
    draft_tours = get_tour_keys_by_status("draft")
    tours_without_photos = {
        tour_key: get_missing_photo_requirements(tour, tour_key)
        for tour_key, tour in TOUR_CATALOG.items()
        if tour.get("status") == "active" and get_missing_photo_requirements(tour, tour_key)
    }
    tours_without_price = [
        tour_key
        for tour_key, tour in TOUR_CATALOG.items()
        if tour.get("status") == "active" and is_missing_price(tour)
    ]
    lead_counts = get_lead_status_counts()
    recommendations = build_recommendations(
        active_tours,
        draft_tours,
        tours_without_photos,
        tours_without_price,
        lead_counts,
    )

    return "\n\n".join(
        [
            format_key_list("Активные туры:", active_tours),
            format_key_list("Draft-туры:", draft_tours),
            format_missing_photos(tours_without_photos),
            format_key_list("Туры без цены:", tours_without_price),
            format_lead_stage_counts(),
            "\n".join(["Что исправить:", *[f"- {item}" for item in recommendations]]),
        ]
    )
