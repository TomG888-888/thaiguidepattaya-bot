import logging
import os
from pathlib import Path
import random
import re
import base64
import hashlib
import html
import secrets
import tempfile
import time
from urllib.parse import urlencode
import zipfile

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response, jsonify, redirect, request
import requests

from ai_manager import generate_reply
from content_manager import generate_expert_post, generate_sales_post, generate_story_post
from database import (
    add_message,
    create_lead,
    get_lead_stage,
    get_leads,
    get_lead_status_counts,
    get_message_count,
    get_published_tour_keys,
    get_published_tours,
    get_recent_messages,
    init_db,
    mark_tour_published,
    mark_event_processed,
    update_lead_stage,
    update_lead_status,
)
from growth_manager import generate_admin_audit, generate_photo_audit
from product_manager import AVAILABLE_TOUR_KEYS, generate_product_card
from seasonal_manager import get_current_season, init_current_season, set_current_season
from tour_catalog import TOUR_CATALOG, get_public_tour, normalize_tour_key


app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
init_db()
init_current_season()

BASE_DIR = Path(__file__).resolve().parent
VK_TOKEN = os.getenv("VK_TOKEN")
USER_VK_TOKEN = os.getenv("USER_VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
VK_MARKET_CATEGORY_ID = os.getenv("VK_MARKET_CATEGORY_ID", "1")
VK_APP_ID = os.getenv("VK_APP_ID")
VK_REDIRECT_URI = os.getenv("VK_REDIRECT_URI")
PUBLIC_BACKEND_URL = os.getenv("PUBLIC_BACKEND_URL")
ADMIN_ID = os.getenv("ADMIN_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AUTO_POSTING_ENABLED = os.getenv("AUTO_POSTING_ENABLED", "false").lower() == "true"
VK_CONFIRMATION_RESPONSE = "dfe8da6d"
VK_API_VERSION = "5.199"
VK_AUTH_SCOPE = "market photos groups wall offline"
PKCE_STATE_TTL_SECONDS = 600
PKCE_STATES = {}
CREATE_PRODUCT_DISABLED_MESSAGE = (
    "Автоматическое создание товаров через VK API сейчас недоступно: "
    "VK требует user token с market/photos, а новое VK ID приложение такие права не выдаёт."
)
AUTO_REPLY_TEXT = """Привет!
Максим на связи.

Скажите пожалуйста:

1. Сколько человек?
2. Какие даты отдыха?
3. Что интереснее:
- острова
- экскурсии
- море

Подберу лучший вариант за 2 минуты."""
ADMIN_HELP_TEXT = """Доступные команды:

/help
/admin_audit
/photo_audit
/photo_export <tour_key>
/stats
/tours
/tour_preview <tour_key>
/published
/not_published
/mark_published <tour_key>
/publish_queue
/leads
/create_product <tour_key>
/post expert
/post sales
/post story
/product <tour_key>
/product_export <tour_key>
/product_export_all
/product_export_drafts
/product_pack <tour_key>
/product_photos <tour_key>
/product_zip <tour_key>
/vk_auth_link
/vk_token_debug
/vk_post_pack <tour_key>
/vk_market_test
/publish expert
/publish sales
/publish story
/season
/season set <season>
/stage <peer_id> <stage>
/booked <peer_id>
/lost <peer_id>
/token_help"""


TOKEN_HELP_TEXT = """USER_VK_TOKEN нужен для автоматического создания товаров VK Market.

1. Создайте VK Standalone-приложение в разделе разработчиков:
https://dev.vk.com/

2. Получите пользовательский токен администратора с правами:
market, photos, groups, wall, offline

3. В Railway откройте Variables и добавьте:
USER_VK_TOKEN=ваш_токен

Для временной авторизации через VK ID используйте команду /vk_auth_link.

Подробная инструкция: docs/vk_user_token.md"""


def format_lead_stats():
    counts = get_lead_status_counts()
    return (
        "Лиды по стадиям:\n"
        f"new: {counts['new']}\n"
        f"qualified: {counts['qualified']}\n"
        f"offer_sent: {counts['offer_sent']}\n"
        f"booked: {counts['booked']}\n"
        f"lost: {counts['lost']}"
    )


def format_leads():
    leads = get_leads()
    if not leads:
        return "Лидов пока нет."

    lines = ["Лиды:"]
    for lead in leads:
        lines.append(
            f"{lead['peer_id']}\n"
            f"{lead['first_contact']}\n"
            f"{lead['status']}"
        )
    return "\n\n".join(lines)


def is_admin(peer_id):
    return bool(ADMIN_ID) and str(peer_id) == ADMIN_ID


def cleanup_pkce_states():
    now = time.time()
    expired_states = [
        state
        for state, data in PKCE_STATES.items()
        if now - data["created_at"] > PKCE_STATE_TTL_SECONDS
    ]
    for state in expired_states:
        PKCE_STATES.pop(state, None)


def create_code_challenge(code_verifier):
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def get_vk_auth_link():
    if not PUBLIC_BACKEND_URL:
        return "PUBLIC_BACKEND_URL не настроен в ENV."

    backend_url = PUBLIC_BACKEND_URL.rstrip("/")
    return f"{backend_url}/vk/auth-start"


def get_vk_auth_debug_url():
    if not VK_APP_ID or not VK_REDIRECT_URI:
        return "VK_APP_ID или VK_REDIRECT_URI не настроены."

    params = {
        "response_type": "code",
        "client_id": VK_APP_ID,
        "redirect_uri": VK_REDIRECT_URI,
        "scope": VK_AUTH_SCOPE,
        "state": "<generated_state>",
        "code_challenge": "<generated_s256_code_challenge>",
        "code_challenge_method": "S256",
    }
    return f"https://id.vk.ru/authorize?{urlencode(params)}"


def render_token_page(access_token):
    escaped_token = html.escape(access_token)
    return Response(
        f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>USER_VK_TOKEN получен</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 40px;
      line-height: 1.5;
      color: #222;
    }}
    textarea {{
      width: 100%;
      max-width: 960px;
      min-height: 180px;
      font-family: monospace;
      font-size: 14px;
    }}
  </style>
</head>
<body>
  <h1>USER_VK_TOKEN получен</h1>
  <p>Скопируйте access_token в Railway Variables.</p>
  <textarea readonly>{escaped_token}</textarea>
</body>
</html>""",
        mimetype="text/html",
    )


def render_oauth_error(message):
    return Response(
        f"Ошибка VK OAuth: {html.escape(message)}",
        status=400,
        mimetype="text/plain",
    )


def get_token_prefix(token):
    if not token:
        return ""
    return f"{token[:8]}..."


def render_vk_token_debug_page(token_data):
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", "")
    user_id = token_data.get("user_id") or token_data.get("id", "")
    scope = token_data.get("scope", "")

    return Response(
        "VK TOKEN EXCHANGE OK\n\n"
        f"access_token prefix={get_token_prefix(access_token)}\n"
        f"refresh_token prefix={get_token_prefix(refresh_token)}\n"
        f"expires_in={expires_in}\n"
        f"user_id={user_id}\n"
        f"scope={scope}",
        mimetype="text/plain",
    )


def parse_status_command(text, command):
    parts = text.split()
    if len(parts) != 2 or parts[0] != command:
        return None

    try:
        return int(parts[1])
    except ValueError:
        return None


def parse_stage_command(text):
    parts = text.split()
    if len(parts) != 3 or parts[0] != "/stage":
        return None

    try:
        peer_id = int(parts[1])
    except ValueError:
        return None

    return peer_id, parts[2]


def parse_season_command(text):
    parts = text.split()
    if parts == ["/season"]:
        return "show", None

    if len(parts) == 3 and parts[0] == "/season" and parts[1] == "set":
        return "set", parts[2]

    return None, None


def generate_admin_post(post_type):
    generators = {
        "expert": generate_expert_post,
        "sales": generate_sales_post,
        "story": generate_story_post,
    }
    generator = generators.get(post_type)
    if not generator:
        return "Неверный тип поста. Используйте: expert, sales или story."

    post = generator()
    if not post:
        return "Не удалось сгенерировать пост."

    return post


def generate_admin_product_card(tour_key):
    product_card = generate_product_card(tour_key)
    if not product_card:
        return f"Не удалось сгенерировать карточку. Используйте: {AVAILABLE_TOUR_KEYS}."

    return product_card


def publish_admin_post(post_type):
    post = generate_admin_post(post_type)
    if post.startswith("Неверный тип поста") or post.startswith("Не удалось"):
        return post

    post_link = publish_vk_wall_post(post)
    if not post_link:
        return "Не удалось опубликовать пост."

    return f"Пост опубликован: {post_link}"


def format_product_export_description(tour):
    lines = [
        tour["short_description"],
        "",
        tour["full_description"],
    ]

    lines.extend(["", "Что включено:", *[f"- {item}" for item in tour["included"]]])

    if tour.get("not_included"):
        lines.extend(["", "Что не включено:", *[f"- {item}" for item in tour["not_included"]]])

    lines.extend(
        [
            "",
            f"Длительность: {tour['duration']}",
            f"Время в пути: {tour['travel_time']}",
            f"Отправление: {tour.get('departure') or 'уточняется при бронировании'}",
            "",
            "Что взять с собой:",
            *[f"- {item}" for item in tour["what_to_bring"]],
        ]
    )

    return "\n".join(lines)


def format_optional_price(price):
    return price if price is not None else "по запросу"


def format_product_price(tour):
    return format_optional_price(tour.get("price_adult") or tour.get("price_from"))


def is_filled_price(price):
    return price is not None and str(price).strip() != ""


def format_price_with_currency(price):
    if not is_filled_price(price):
        return "по запросу"

    normalized_price = str(price).strip()
    normalized_price_lower = normalized_price.lower()
    if normalized_price_lower == "по запросу" or "бат" in normalized_price_lower or "thb" in normalized_price_lower:
        return normalized_price

    return f"{normalized_price} бат"


def format_product_export_price(tour):
    price_adult = tour.get("price_adult")
    price_child = tour.get("price_child")

    if is_filled_price(price_adult):
        lines = [f"взрослый — {format_price_with_currency(price_adult)}"]
        if is_filled_price(price_child):
            lines.append(f"ребёнок — {format_price_with_currency(price_child)}")
        return "\n".join(lines)

    return format_price_with_currency(tour.get("price_from"))


def format_required_photos(tour):
    required_photos = (tour.get("photos") or {}).get("required") or []
    if not required_photos:
        return "нет"

    return "\n".join(f"- {item}" for item in required_photos)


def get_product_photo_lines(tour):
    photos = tour.get("photos") or {}
    cover = photos.get("cover")
    gallery = photos.get("gallery") or []
    photo_values = [
        ("Обложка", cover),
        ("Галерея 1", gallery[0] if len(gallery) > 0 else ""),
        ("Галерея 2", gallery[1] if len(gallery) > 1 else ""),
        ("Галерея 3", gallery[2] if len(gallery) > 2 else ""),
        ("Галерея 4", gallery[3] if len(gallery) > 3 else ""),
    ]

    if not all(photo_path for _, photo_path in photo_values):
        return []

    return [f"{label}: {photo_path}" for label, photo_path in photo_values]


def format_product_photos(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour = get_public_tour(normalized_tour_key)
    if not tour:
        return f"Неизвестный тур. Используйте: {AVAILABLE_TOUR_KEYS}."

    photo_lines = get_product_photo_lines(tour)
    if not photo_lines:
        return "Фото не заполнены."

    return "\n".join(["Фото:", *photo_lines])


def format_product_export(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour = get_public_tour(normalized_tour_key)
    if not tour:
        return f"Неизвестный тур. Используйте: {AVAILABLE_TOUR_KEYS}."

    return (
        f"Название товара:\n{tour['title']}\n\n"
        f"Описание товара:\n{format_product_export_description(tour)}\n\n"
        f"Цена:\n{format_product_export_price(tour)}"
    )


def format_product_pack_text(tour):
    not_included = tour.get("not_included") or []
    return (
        f"Название товара:\n{tour['title']}\n\n"
        f"Цена:\n{format_product_export_price(tour)}\n\n"
        f"Описание:\n{tour['short_description']}\n\n{tour['full_description']}\n\n"
        f"Что включено:\n"
        f"{chr(10).join(f'- {item}' for item in tour['included'])}\n\n"
        f"Что не включено:\n"
        f"{chr(10).join(f'- {item}' for item in not_included) if not_included else 'уточняется при бронировании'}\n\n"
        f"Длительность:\n{tour['duration']}\n\n"
        f"Отправление:\n{tour.get('departure') or 'уточняется при бронировании'}\n\n"
        f"Что взять с собой:\n"
        f"{chr(10).join(f'- {item}' for item in tour['what_to_bring'])}"
    )


def get_product_pack_photo_slots(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    photo_dir = BASE_DIR / "static" / "tours" / normalized_tour_key
    return [
        ("cover.jpg", photo_dir / "cover.jpg"),
        ("gallery_1.jpg", photo_dir / "gallery_1.jpg"),
        ("gallery_2.jpg", photo_dir / "gallery_2.jpg"),
        ("gallery_3.jpg", photo_dir / "gallery_3.jpg"),
        ("gallery_4.jpg", photo_dir / "gallery_4.jpg"),
    ]


def get_missing_product_photo_filenames(tour_key):
    return [
        filename
        for filename, photo_path in get_product_pack_photo_slots(tour_key)
        if not photo_path.exists()
    ]


def format_photo_status(tour_key):
    missing_files = get_missing_product_photo_filenames(tour_key)
    if not missing_files:
        return "📷 Фото: OK"

    return "\n".join(
        [
            "📷 Фото: MISSING",
            *[f"MISSING: {filename}" for filename in missing_files],
        ]
    )


def format_product_pack(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour = get_public_tour(normalized_tour_key)
    if not tour:
        return f"Неизвестный тур. Используйте: {AVAILABLE_TOUR_KEYS}."

    pack = [{"type": "text", "text": format_product_pack_text(tour)}]
    for filename, photo_path in get_product_pack_photo_slots(normalized_tour_key):
        if photo_path.exists():
            pack.append(
                {
                    "type": "photo",
                    "path": str(photo_path),
                    "label": filename,
                }
            )
        else:
            pack.append({"type": "text", "text": f"{filename}: MISSING"})

    return pack


def format_vk_post_text(tour):
    included_preview = tour.get("included") or []
    tags = tour.get("tags") or []
    tag_line = " ".join(f"#{tag}" for tag in tags[:8])

    lines = [
        tour["title"],
        "",
        tour["short_description"],
        "",
        tour["full_description"],
        "",
        f"Цена: {format_product_export_price(tour)}",
        f"Длительность: {tour['duration']}",
        f"Отправление: {tour.get('departure') or 'уточняется при бронировании'}",
    ]

    if included_preview:
        lines.extend(["", "Что включено:", *[f"- {item}" for item in included_preview]])

    lines.extend(
        [
            "",
            "Чтобы подобрать дату и формат, напишите в сообщения группы.",
            "Максим подскажет лучший вариант под ваш отдых.",
        ]
    )

    if tag_line:
        lines.extend(["", tag_line])

    return "\n".join(lines)


def format_tour_preview(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour = get_public_tour(normalized_tour_key)
    if not tour:
        return f"Неизвестный тур. Используйте: {AVAILABLE_TOUR_KEYS}."

    return (
        f"TOUR PREVIEW: {normalized_tour_key}\n\n"
        f"Карточка товара:\n{format_product_pack_text(tour)}\n\n"
        "--------------------\n\n"
        f"VK-пост:\n{format_vk_post_text(tour)}\n\n"
        "--------------------\n\n"
        f"{format_photo_status(normalized_tour_key)}"
    )


def create_product_zip(tour_key, zip_dir):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour = get_public_tour(normalized_tour_key)
    if not tour:
        return None, f"Неизвестный тур. Используйте: {AVAILABLE_TOUR_KEYS}."

    zip_path = Path(zip_dir) / f"product_{normalized_tour_key}.zip"
    product_text_lines = [format_product_pack_text(tour)]
    photo_slots = get_product_pack_photo_slots(normalized_tour_key)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, photo_path in photo_slots:
            if photo_path.exists():
                archive.write(photo_path, arcname=filename)
            else:
                product_text_lines.append(f"MISSING: {filename}")

        archive.writestr("product.txt", "\n\n".join(product_text_lines))

    return zip_path, None


def sanitize_telegram_error(value):
    text = str(value)
    if TELEGRAM_BOT_TOKEN:
        text = text.replace(TELEGRAM_BOT_TOKEN, "[hidden_telegram_token]")
    return text


def send_telegram_document(document_path, caption=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не настроены."

    try:
        with Path(document_path).open("rb") as document:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": caption or "",
                },
                files={
                    "document": (Path(document_path).name, document, "application/zip"),
                },
                timeout=30,
            )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as error:
        app.logger.exception("Telegram sendDocument request failed")
        return False, f"Ошибка Telegram sendDocument: {sanitize_telegram_error(error)}"
    except ValueError:
        app.logger.exception("Telegram sendDocument returned non-JSON response")
        return False, "Telegram вернул не-JSON ответ."

    if not result.get("ok"):
        app.logger.error("Telegram sendDocument error: %s", result)
        return False, f"Telegram error: {result.get('description') or result}"

    return True, "ZIP отправлен в Telegram."


def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не настроены."

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
            },
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as error:
        app.logger.exception("Telegram sendMessage request failed")
        return False, f"Ошибка Telegram sendMessage: {sanitize_telegram_error(error)}"
    except ValueError:
        app.logger.exception("Telegram sendMessage returned non-JSON response")
        return False, "Telegram вернул не-JSON ответ."

    if not result.get("ok"):
        app.logger.error("Telegram sendMessage error: %s", result)
        return False, f"Telegram error: {result.get('description') or result}"

    return True, "Сообщение отправлено в Telegram."


def send_telegram_photo(photo_path, caption=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не настроены."

    photo_path = Path(photo_path)
    if not photo_path.exists():
        return False, f"{photo_path.name}: MISSING"

    try:
        with photo_path.open("rb") as photo_file:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": caption or "",
                },
                files={
                    "photo": (photo_path.name, photo_file, "image/jpeg"),
                },
                timeout=30,
            )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as error:
        app.logger.exception("Telegram sendPhoto request failed: %s", photo_path)
        return False, f"Ошибка Telegram sendPhoto: {sanitize_telegram_error(error)}"
    except ValueError:
        app.logger.exception("Telegram sendPhoto returned non-JSON response: %s", photo_path)
        return False, "Telegram вернул не-JSON ответ."

    if not result.get("ok"):
        app.logger.error("Telegram sendPhoto error: %s", result)
        return False, f"Telegram error: {result.get('description') or result}"

    return True, f"{photo_path.name}: OK"


def send_product_zip(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path, error = create_product_zip(normalized_tour_key, temp_dir)
        if error:
            return error

        ok, message = send_telegram_document(
            zip_path,
            caption=f"Product ZIP: {normalized_tour_key}",
        )
        return message if ok else message


def send_vk_post_pack(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour = get_public_tour(normalized_tour_key)
    if not tour:
        return f"Неизвестный тур. Используйте: {AVAILABLE_TOUR_KEYS}."

    ok, message = send_telegram_message(format_vk_post_text(tour))
    if not ok:
        return message

    sent_count = 0
    missing = []
    errors = []
    for filename, photo_path in get_product_pack_photo_slots(normalized_tour_key):
        if not photo_path.exists():
            missing_message = f"{filename}: MISSING"
            missing.append(missing_message)
            ok, error_message = send_telegram_message(missing_message)
            if not ok:
                errors.append(error_message)
            continue

        ok, photo_message = send_telegram_photo(photo_path, caption=filename)
        if ok:
            sent_count += 1
        else:
            errors.append(photo_message)

    if errors:
        return "VK post pack отправлен частично:\n" + "\n".join(errors)

    result_lines = [
        "VK post pack отправлен в Telegram.",
        f"Фото отправлено: {sent_count}",
    ]
    if missing:
        result_lines.extend(missing)

    return "\n".join(result_lines)


def safe_format_product_export(tour_key):
    try:
        return format_product_export(tour_key)
    except Exception as error:
        app.logger.exception("product_export failed for tour_key=%s", tour_key)
        return f"Ошибка product_export: {error}"


def get_market_price(tour):
    price = tour.get("price_adult") if is_filled_price(tour.get("price_adult")) else tour.get("price_from")
    if not is_filled_price(price):
        return None

    normalized_price = str(price).strip().lower().replace("бат", "").replace("thb", "").strip()
    normalized_price = normalized_price.replace(" ", "").replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", normalized_price):
        return None

    return normalized_price


def get_product_photo_paths(tour):
    photos = tour.get("photos") or {}
    cover = photos.get("cover")
    gallery = photos.get("gallery") or []
    photo_paths = [
        cover,
        gallery[0] if len(gallery) > 0 else "",
        gallery[1] if len(gallery) > 1 else "",
        gallery[2] if len(gallery) > 2 else "",
        gallery[3] if len(gallery) > 3 else "",
    ]

    if not all(photo_paths):
        return []

    local_paths = []
    for photo_path in photo_paths:
        if not photo_path.startswith("/static/"):
            return []

        local_path = BASE_DIR / photo_path.lstrip("/")
        if not local_path.exists():
            return []
        local_paths.append(local_path)

    return local_paths


def call_vk_api(method, token, params=None):
    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data={
                "access_token": token,
                "v": VK_API_VERSION,
                **(params or {}),
            },
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as error:
        raise RuntimeError(f"VK API request failed: {method}: {error}") from error
    except ValueError as error:
        raise RuntimeError(f"VK API returned non-JSON response: {method}") from error

    if "error" in result:
        raise RuntimeError(f"VK API error {method}: {result['error']}")

    return result.get("response")


def sanitize_token_debug_text(value):
    text = str(value)
    if USER_VK_TOKEN:
        text = text.replace(USER_VK_TOKEN, "[hidden_token]")
    return re.sub(r"('access_token',\s*')[^']+", r"\1[hidden_token]", text)


def call_vk_api_for_debug(method):
    try:
        response = requests.post(
            f"https://api.vk.com/method/{method}",
            data={
                "access_token": USER_VK_TOKEN,
                "v": VK_API_VERSION,
            },
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as error:
        return f"ERROR: {sanitize_token_debug_text(error)}"
    except ValueError:
        return "ERROR: non-JSON response"

    if "error" in result:
        return f"ERROR: {sanitize_token_debug_text(result['error'])}"

    return sanitize_token_debug_text(result.get("response"))


def format_vk_token_debug():
    if not USER_VK_TOKEN:
        return "USER_VK_TOKEN не настроен."

    users_result = call_vk_api_for_debug("users.get")
    profile_result = call_vk_api_for_debug("account.getProfileInfo")
    combined_errors = f"{users_result}\n{profile_result}".lower()

    if "anonymous" in combined_errors:
        scope_status = "VK вернул ошибку anonymous token. Вероятно, токен не пользовательский или без нужных прав."
    elif "access_token" in combined_errors or "permission" in combined_errors:
        scope_status = "VK вернул ошибку доступа. Проверьте тип токена и scope: market, photos, groups, wall."
    else:
        scope_status = "Явной ошибки anonymous token не найдено."

    return (
        "VK token debug:\n"
        f"token prefix: {USER_VK_TOKEN[:8]}\n"
        f"token length: {len(USER_VK_TOKEN)}\n\n"
        f"users.get:\n{users_result}\n\n"
        f"account.getProfileInfo:\n{profile_result}\n\n"
        f"scopes/anonymous:\n{scope_status}\n\n"
        "auth-start URL:\n"
        f"{get_vk_auth_debug_url()}\n\n"
        f"scope: {VK_AUTH_SCOPE}\n"
        f"redirect_uri: {VK_REDIRECT_URI or '<NOT SET>'}"
    )


def upload_market_photo(photo_path, group_id, main_photo):
    upload_server = call_vk_api(
        "photos.getMarketUploadServer",
        USER_VK_TOKEN,
        {
            "group_id": group_id,
            "main_photo": 1 if main_photo else 0,
        },
    )
    upload_url = upload_server.get("upload_url") if isinstance(upload_server, dict) else None
    if not upload_url:
        raise RuntimeError("VK did not return market photo upload_url")

    try:
        with photo_path.open("rb") as photo_file:
            upload_response = requests.post(
                upload_url,
                files={"file0": (photo_path.name, photo_file, "image/jpeg")},
                timeout=30,
            )
        upload_response.raise_for_status()
        upload_result = upload_response.json()
    except requests.RequestException as error:
        raise RuntimeError(f"VK market photo upload failed: {photo_path.name}: {error}") from error
    except ValueError as error:
        raise RuntimeError(f"VK market photo upload returned non-JSON response: {photo_path.name}") from error

    saved_photos = call_vk_api(
        "photos.saveMarketPhoto",
        USER_VK_TOKEN,
        {
            **upload_result,
            "group_id": group_id,
            "main_photo": 1 if main_photo else 0,
        },
    )
    if not saved_photos:
        raise RuntimeError(f"VK did not save market photo: {photo_path.name}")

    photo = saved_photos[0] if isinstance(saved_photos, list) else saved_photos
    photo_id = photo.get("id") if isinstance(photo, dict) else None
    if not photo_id:
        raise RuntimeError(f"VK saved market photo without id: {photo_path.name}")

    return photo_id


def create_vk_market_product(tour_key):
    if not USER_VK_TOKEN:
        return "Для автоматического создания товаров нужен USER_VK_TOKEN администратора."

    if not VK_GROUP_ID:
        return "Не указан VK_GROUP_ID."

    normalized_tour_key = normalize_tour_key(tour_key)
    tour = get_public_tour(normalized_tour_key)
    if not tour:
        return f"Неизвестный тур. Используйте: {AVAILABLE_TOUR_KEYS}."

    price = get_market_price(tour)
    if not price:
        return "Для создания товара нужна числовая цена."

    try:
        group_id = int(VK_GROUP_ID)
        category_id = int(VK_MARKET_CATEGORY_ID)
    except ValueError:
        return "VK_GROUP_ID и VK_MARKET_CATEGORY_ID должны быть числами."

    photo_paths = get_product_photo_paths(tour)
    if len(photo_paths) != 5:
        return "Фото не заполнены."

    try:
        app.logger.info("VK market product creation started: tour_key=%s", normalized_tour_key)
        main_photo_id = upload_market_photo(photo_paths[0], group_id, main_photo=True)
        gallery_photo_ids = [
            upload_market_photo(photo_path, group_id, main_photo=False)
            for photo_path in photo_paths[1:]
        ]
        product = call_vk_api(
            "market.add",
            USER_VK_TOKEN,
            {
                "owner_id": -group_id,
                "name": tour["title"],
                "description": format_product_export_description(tour),
                "category_id": category_id,
                "price": price,
                "main_photo_id": main_photo_id,
                "photo_ids": ",".join(str(photo_id) for photo_id in gallery_photo_ids),
            },
        )
    except Exception as error:
        app.logger.exception("VK market product creation failed: tour_key=%s", normalized_tour_key)
        return f"Ошибка create_product: {error}"

    item_id = product.get("market_item_id") or product.get("item_id") if isinstance(product, dict) else None
    if not item_id:
        app.logger.error("VK market.add response without item id: %s", product)
        return f"Товар создан, но VK не вернул ID товара: {product}"

    product_link = f"https://vk.com/market-{group_id}?w=product-{group_id}_{item_id}"
    app.logger.info("VK market product created: tour_key=%s, item_id=%s", normalized_tour_key, item_id)
    return f"Товар создан: {product_link}"


def test_vk_market_access():
    if not USER_VK_TOKEN:
        return "Для автоматического создания товаров нужен USER_VK_TOKEN администратора."

    if not VK_GROUP_ID:
        return "Не указан VK_GROUP_ID."

    try:
        group_id = int(VK_GROUP_ID)
        category_id = int(VK_MARKET_CATEGORY_ID)
    except ValueError:
        return "VK_GROUP_ID и VK_MARKET_CATEGORY_ID должны быть числами."

    try:
        market_response = call_vk_api(
            "market.get",
            USER_VK_TOKEN,
            {
                "owner_id": -group_id,
                "count": 1,
            },
        )
        upload_response = call_vk_api(
            "photos.getMarketUploadServer",
            USER_VK_TOKEN,
            {
                "group_id": group_id,
                "main_photo": 1,
            },
        )
    except Exception as error:
        app.logger.exception("VK market test failed")
        return f"Ошибка vk_market_test: {error}"

    market_count = market_response.get("count") if isinstance(market_response, dict) else "unknown"
    upload_url_status = "OK" if isinstance(upload_response, dict) and upload_response.get("upload_url") else "MISSING"

    return (
        "VK Market test:\n"
        "USER_VK_TOKEN: OK\n"
        f"VK_GROUP_ID: {group_id}\n"
        f"VK_MARKET_CATEGORY_ID: {category_id}\n"
        f"market.get: OK, товаров: {market_count}\n"
        f"photos.getMarketUploadServer: {upload_url_status}"
    )


def split_export_messages(exports, max_length=3500):
    messages = []
    current_message = ""
    for export in exports:
        candidate = export if not current_message else f"{current_message}\n\n---\n\n{export}"
        if len(candidate) <= max_length:
            current_message = candidate
            continue

        if current_message:
            messages.append(current_message)
        current_message = export

    if current_message:
        messages.append(current_message)

    return messages


def format_product_exports_by_status(status):
    exports = [
        format_product_export(tour_key)
        for tour_key, tour in TOUR_CATALOG.items()
        if tour.get("status") == status
    ]
    if not exports:
        return [f"Товаров со статусом {status} нет."]

    return split_export_messages(exports)


def format_all_product_exports():
    return format_product_exports_by_status("active")


def format_draft_product_exports():
    return format_product_exports_by_status("draft")


def format_tours_list():
    lines = ["Туры:"]
    for tour_key, tour in sorted(TOUR_CATALOG.items()):
        photo_status = "OK" if not get_missing_product_photo_filenames(tour_key) else "MISSING"
        lines.append(
            f"{tour_key}\n"
            f"{tour['title']}\n"
            f"Цена: {format_product_export_price(tour)}\n"
            f"Фото: {photo_status}"
        )

    return "\n\n".join(lines)


def format_published_tours():
    published_tours = get_published_tours()
    if not published_tours:
        return "Опубликованных туров пока нет."

    lines = ["Опубликованные туры:"]
    for published_tour in published_tours:
        tour_key = published_tour["tour_key"]
        tour = get_public_tour(tour_key)
        title = tour["title"] if tour else "(нет в каталоге)"
        lines.append(
            f"{tour_key}\n"
            f"{title}\n"
            f"{published_tour['published_at']}"
        )

    return "\n\n".join(lines)


def format_not_published_tours():
    published_keys = get_published_tour_keys()
    lines = ["Неопубликованные туры:"]
    for tour_key, tour in sorted(TOUR_CATALOG.items()):
        if tour_key in published_keys:
            continue

        photo_status = "OK" if not get_missing_product_photo_filenames(tour_key) else "MISSING"
        lines.append(
            f"{tour_key}\n"
            f"{tour['title']}\n"
            f"Цена: {format_product_export_price(tour)}\n"
            f"Фото: {photo_status}"
        )

    if len(lines) == 1:
        return "Все туры опубликованы."

    return "\n\n".join(lines)


def mark_catalog_tour_published(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    if not get_public_tour(normalized_tour_key):
        return f"Неизвестный тур. Используйте: {AVAILABLE_TOUR_KEYS}."

    mark_tour_published(normalized_tour_key)
    return f"✅ Published: {normalized_tour_key}"


def has_publishable_price(tour):
    price = format_product_export_price(tour).strip().lower()
    return bool(price) and "по запросу" not in price


def get_publish_queue_reasons(tour_key, tour):
    reasons = []
    missing_photos = get_missing_product_photo_filenames(tour_key)
    reasons.extend(f"нет фото: {filename}" for filename in missing_photos)

    if not str(tour.get("title") or "").strip():
        reasons.append("нет названия")

    if not has_publishable_price(tour):
        reasons.append("нет цены")

    if not str(tour.get("short_description") or tour.get("full_description") or "").strip():
        reasons.append("нет описания")

    return reasons


def format_publish_queue_tour(tour_key, tour, status):
    return (
        f"{tour_key}\n"
        f"{tour.get('title') or 'нет названия'}\n"
        f"Цена: {format_product_export_price(tour)}\n"
        f"{status}"
    )


def format_publish_queue():
    published_tours = get_published_tours()
    published_map = {
        published_tour["tour_key"]: published_tour["published_at"]
        for published_tour in published_tours
    }
    ready = []
    not_ready = []
    published = []

    for tour_key, tour in sorted(TOUR_CATALOG.items()):
        if tour_key in published_map:
            published.append(
                format_publish_queue_tour(
                    tour_key,
                    tour,
                    f"published_at: {published_map[tour_key]}",
                )
            )
            continue

        reasons = get_publish_queue_reasons(tour_key, tour)
        if reasons:
            not_ready.append(
                format_publish_queue_tour(
                    tour_key,
                    tour,
                    "Причины:\n" + "\n".join(f"- {reason}" for reason in reasons),
                )
            )
        else:
            ready.append(format_publish_queue_tour(tour_key, tour, "Готов к публикации"))

    return "\n\n".join(
        [
            "✅ ГОТОВЫ К ПУБЛИКАЦИИ",
            "\n\n".join(ready) if ready else "Нет",
            "",
            "⚠️ НЕ ГОТОВЫ",
            "\n\n".join(not_ready) if not_ready else "Нет",
            "",
            "📌 УЖЕ ОПУБЛИКОВАНЫ",
            "\n\n".join(published) if published else "Нет",
        ]
    )


def publish_scheduled_post(post_type):
    app.logger.info("Scheduled post started: %s", post_type)

    post = generate_admin_post(post_type)
    if post.startswith("Неверный тип поста") or post.startswith("Не удалось"):
        app.logger.error("Scheduled post generation failed: %s", post)
        return

    post_link = publish_vk_wall_post(post)
    if not post_link:
        app.logger.error("Scheduled post publishing failed: %s", post_type)
        return

    app.logger.info("Scheduled post published: %s", post_link)


def has_people_count(text):
    normalized_text = text.lower()
    if re.search(r"\b\d+\s*(человек|чел|персон|гост|турист)", normalized_text):
        return True

    return bool(
        re.search(
            r"\b(один|одна|двое|два|трое|три|четверо|четыре|пятеро|пять|шестеро|шесть)\b",
            normalized_text,
        )
    )


def has_travel_dates(text):
    normalized_text = text.lower()
    month_names = (
        "январ",
        "феврал",
        "март",
        "апрел",
        "май",
        "июн",
        "июл",
        "август",
        "сентябр",
        "октябр",
        "ноябр",
        "декабр",
    )

    if re.search(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b", normalized_text):
        return True

    if re.search(r"\b\d{1,2}\s*[-–]\s*\d{1,2}\b", normalized_text) and any(
        month in normalized_text for month in month_names
    ):
        return True

    return bool(
        re.search(r"\b\d{1,2}\s+", normalized_text)
        and any(month in normalized_text for month in month_names)
    )


def is_qualified_message(text):
    return has_people_count(text) and has_travel_dates(text)


def is_tour_offer(text):
    normalized_text = text.lower()
    offer_words = (
        "предлагаю",
        "вариант",
        "подойдет",
        "подойдёт",
        "рекомендую",
        "тур",
        "экскурси",
        "остров",
        "маршрут",
        "стоимость",
        "цена",
        "бат",
        "thb",
    )

    return any(word in normalized_text for word in offer_words)


def handle_admin_command(peer_id, text):
    if not text.startswith(
        (
            "/help",
            "/admin_audit",
            "/photo_audit",
            "/photo_export",
            "/stats",
            "/tour_preview",
            "/tours",
            "/published",
            "/not_published",
            "/mark_published",
            "/publish_queue",
            "/leads",
            "/create_product",
            "/post",
            "/product",
            "/publish",
            "/vk_market_test",
            "/vk_auth_link",
            "/vk_token_debug",
            "/vk_post_pack",
            "/token_help",
            "/season",
            "/stage",
            "/booked",
            "/lost",
        )
    ):
        return None

    if not is_admin(peer_id):
        app.logger.warning("Unauthorized admin command from peer_id=%s: %s", peer_id, text)
        return "Команда доступна только администратору."

    if text == "/help":
        return ADMIN_HELP_TEXT

    if text == "/token_help":
        return TOKEN_HELP_TEXT

    if text == "/vk_auth_link":
        return get_vk_auth_link()

    if text == "/vk_token_debug":
        return format_vk_token_debug()

    if text.startswith("/vk_post_pack"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /vk_post_pack samet_1d_lunch."
        return send_vk_post_pack(parts[1])

    if text == "/admin_audit":
        return generate_admin_audit()

    if text == "/photo_audit":
        return generate_photo_audit()

    if text.startswith("/photo_export"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /photo_export samet_1d_lunch."
        return format_product_photos(parts[1])

    if text == "/stats":
        return format_lead_stats()

    if text.startswith("/tour_preview"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /tour_preview samet_1d_lunch."
        return format_tour_preview(parts[1])

    if text == "/tours":
        return format_tours_list()

    if text == "/published":
        return format_published_tours()

    if text == "/not_published":
        return format_not_published_tours()

    if text.startswith("/mark_published"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /mark_published samet_1d_lunch."
        return mark_catalog_tour_published(parts[1])

    if text == "/publish_queue":
        return format_publish_queue()

    if text == "/leads":
        return format_leads()

    if text.startswith("/create_product"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /create_product samet_2d_silver_sand."
        return CREATE_PRODUCT_DISABLED_MESSAGE

    if text == "/vk_market_test":
        return test_vk_market_access()

    season_action, season = parse_season_command(text)
    if season_action == "show":
        return f"Текущий сезон: {get_current_season()}"

    if season_action == "set":
        if set_current_season(season):
            return f"Сезон изменен: {get_current_season()}"
        return "Неверный сезон. Используйте: high, low или rainy."

    if text.startswith("/post"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /post expert, /post sales или /post story."
        return generate_admin_post(parts[1])

    if text.startswith("/product_export_all"):
        if text != "/product_export_all":
            return "Неверный формат команды. Используйте /product_export_all."
        return format_all_product_exports()

    if text.startswith("/product_export_drafts"):
        if text != "/product_export_drafts":
            return "Неверный формат команды. Используйте /product_export_drafts."
        return format_draft_product_exports()

    if text.startswith("/product_export"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /product_export samet_1d_lunch."
        return safe_format_product_export(parts[1])

    if text.startswith("/product_pack"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /product_pack samet_1d_lunch."
        return format_product_pack(parts[1])

    if text.startswith("/product_zip"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /product_zip samet_1d_lunch."
        return send_product_zip(parts[1])

    if text.startswith("/product_photos"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /product_photos samet_1d_lunch."
        return format_product_photos(parts[1])

    if text.startswith("/product"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /product samet_1d_lunch."
        return generate_admin_product_card(parts[1])

    if text.startswith("/publish_product"):
        return "Команда /publish_product отключена. Используйте /product_export <tour_key>."

    if text.startswith("/publish"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /publish expert, /publish sales или /publish story."
        return publish_admin_post(parts[1])

    stage_command = parse_stage_command(text)
    if stage_command is not None:
        lead_peer_id, stage = stage_command
        if update_lead_stage(lead_peer_id, stage):
            return f"Лид {lead_peer_id} переведен в {stage}."
        return f"Не удалось изменить стадию лида {lead_peer_id}."

    booked_peer_id = parse_status_command(text, "/booked")
    if booked_peer_id is not None:
        if update_lead_status(booked_peer_id, "booked"):
            return f"Лид {booked_peer_id} переведен в booked"
        return f"Лид {booked_peer_id} не найден."

    lost_peer_id = parse_status_command(text, "/lost")
    if lost_peer_id is not None:
        if update_lead_status(lost_peer_id, "lost"):
            return f"Лид {lost_peer_id} переведен в lost"
        return f"Лид {lost_peer_id} не найден."

    return "Неверный формат команды."


def get_event_key(payload, message):
    event_id = payload.get("event_id")
    if event_id:
        return f"event:{event_id}"

    message_id = message.get("id")
    if message_id:
        return f"message:{message_id}"

    conversation_message_id = message.get("conversation_message_id")
    peer_id = message.get("peer_id")
    if conversation_message_id and peer_id:
        return f"conversation:{peer_id}:{conversation_message_id}"

    return None


def send_vk_message(peer_id, message):
    if not VK_TOKEN:
        app.logger.error("VK_TOKEN is not configured")
        return False

    try:
        app.logger.info("VK messages.send started: peer_id=%s, length=%s", peer_id, len(message))
        response = requests.post(
            "https://api.vk.com/method/messages.send",
            data={
                "access_token": VK_TOKEN,
                "v": VK_API_VERSION,
                "peer_id": peer_id,
                "message": message,
                "random_id": random.randint(1, 2_147_483_647),
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        app.logger.exception("VK messages.send request failed")
        return False

    try:
        result = response.json()
    except ValueError:
        app.logger.exception("VK messages.send returned non-JSON response: %s", response.text)
        return False

    if "error" in result:
        app.logger.error("VK messages.send error: %s", result["error"])
        return False

    app.logger.info("VK messages.send success: peer_id=%s, response=%s", peer_id, result.get("response"))
    return True


def send_vk_photo_message(peer_id, photo_path):
    if not VK_TOKEN:
        app.logger.error("VK_TOKEN is not configured")
        return False

    photo_path = Path(photo_path)
    if not photo_path.exists():
        app.logger.error("VK photo path does not exist: %s", photo_path)
        return False

    try:
        upload_server = call_vk_api(
            "photos.getMessagesUploadServer",
            VK_TOKEN,
            {"peer_id": peer_id},
        )
        upload_url = upload_server.get("upload_url") if isinstance(upload_server, dict) else None
        if not upload_url:
            app.logger.error("VK messages photo upload_url is missing")
            return False

        with photo_path.open("rb") as photo_file:
            upload_response = requests.post(
                upload_url,
                files={"photo": (photo_path.name, photo_file, "image/jpeg")},
                timeout=30,
            )
        upload_response.raise_for_status()
        upload_result = upload_response.json()

        saved_photos = call_vk_api(
            "photos.saveMessagesPhoto",
            VK_TOKEN,
            upload_result,
        )
    except requests.RequestException:
        app.logger.exception("VK photo upload request failed: %s", photo_path)
        return False
    except ValueError:
        app.logger.exception("VK photo upload returned non-JSON response: %s", photo_path)
        return False
    except Exception:
        app.logger.exception("VK photo send failed: %s", photo_path)
        return False

    photo = saved_photos[0] if isinstance(saved_photos, list) and saved_photos else None
    if not isinstance(photo, dict) or not photo.get("owner_id") or not photo.get("id"):
        app.logger.error("VK saveMessagesPhoto response without photo id: %s", saved_photos)
        return False

    attachment = f"photo{photo['owner_id']}_{photo['id']}"
    if photo.get("access_key"):
        attachment = f"{attachment}_{photo['access_key']}"

    try:
        response = requests.post(
            "https://api.vk.com/method/messages.send",
            data={
                "access_token": VK_TOKEN,
                "v": VK_API_VERSION,
                "peer_id": peer_id,
                "attachment": attachment,
                "random_id": random.randint(1, 2_147_483_647),
            },
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException:
        app.logger.exception("VK photo messages.send request failed: %s", photo_path)
        return False
    except ValueError:
        app.logger.exception("VK photo messages.send returned non-JSON response: %s", photo_path)
        return False

    if "error" in result:
        app.logger.error("VK photo messages.send error: %s", result["error"])
        return False

    app.logger.info("VK photo messages.send success: peer_id=%s, photo=%s", peer_id, photo_path.name)
    return True


def publish_vk_wall_post(message):
    if not VK_TOKEN:
        app.logger.error("VK_TOKEN is not configured")
        return None

    if not VK_GROUP_ID:
        app.logger.error("VK_GROUP_ID is not configured")
        return None

    try:
        group_id = int(VK_GROUP_ID)
    except ValueError:
        app.logger.error("VK_GROUP_ID must be an integer")
        return None

    try:
        response = requests.post(
            "https://api.vk.com/method/wall.post",
            data={
                "access_token": VK_TOKEN,
                "v": VK_API_VERSION,
                "owner_id": -group_id,
                "from_group": 1,
                "message": message,
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        app.logger.exception("VK wall.post request failed")
        return None

    result = response.json()
    if "error" in result:
        app.logger.error("VK wall.post error: %s", result["error"])
        return None

    post_id = result.get("response", {}).get("post_id")
    if not post_id:
        app.logger.error("VK wall.post response without post_id: %s", result)
        return None

    return f"https://vk.com/wall-{group_id}_{post_id}"


def start_scheduler():
    if not AUTO_POSTING_ENABLED:
        app.logger.info("Auto posting scheduler is disabled")
        return None

    scheduler = BackgroundScheduler(timezone="Asia/Bangkok")
    scheduler.add_job(
        publish_scheduled_post,
        "cron",
        day_of_week="mon",
        hour=10,
        minute=0,
        args=["expert"],
        id="auto_post_expert_monday",
        replace_existing=True,
    )
    scheduler.add_job(
        publish_scheduled_post,
        "cron",
        day_of_week="wed",
        hour=10,
        minute=0,
        args=["story"],
        id="auto_post_story_wednesday",
        replace_existing=True,
    )
    scheduler.add_job(
        publish_scheduled_post,
        "cron",
        day_of_week="fri",
        hour=10,
        minute=0,
        args=["sales"],
        id="auto_post_sales_friday",
        replace_existing=True,
    )
    scheduler.start()
    app.logger.info("Auto posting scheduler started")
    return scheduler


scheduler = start_scheduler()


@app.route("/")
def index():
    return jsonify(
        {
            "status": "ok",
            "service": "thaiguidepattaya-bot",
            "vk_group_id": VK_GROUP_ID,
            "vk_token_configured": bool(VK_TOKEN),
        }
    )


@app.route("/vk/auth-start")
def vk_auth_start():
    if not VK_APP_ID:
        return render_oauth_error("VK_APP_ID не настроен в ENV.")

    if not VK_REDIRECT_URI:
        return render_oauth_error("VK_REDIRECT_URI не настроен в ENV.")

    cleanup_pkce_states()

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = create_code_challenge(code_verifier)
    state = secrets.token_urlsafe(32)
    PKCE_STATES[state] = {
        "code_verifier": code_verifier,
        "created_at": time.time(),
    }

    params = {
        "response_type": "code",
        "client_id": VK_APP_ID,
        "redirect_uri": VK_REDIRECT_URI,
        "scope": VK_AUTH_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"https://id.vk.ru/authorize?{urlencode(params)}"
    app.logger.info("VK OAuth PKCE auth started")
    return redirect(auth_url)


@app.route("/vk/callback")
def vk_auth_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    device_id = request.args.get("device_id")

    if not code:
        return render_oauth_error("VK не вернул code.")

    if not state:
        return render_oauth_error("VK не вернул state.")

    cleanup_pkce_states()
    state_data = PKCE_STATES.pop(state, None)
    if not state_data:
        return render_oauth_error("state не найден или истек. Запустите авторизацию заново.")

    if not VK_APP_ID:
        return render_oauth_error("VK_APP_ID не настроен в ENV.")

    if not VK_REDIRECT_URI:
        return render_oauth_error("VK_REDIRECT_URI не настроен в ENV.")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": VK_APP_ID,
        "redirect_uri": VK_REDIRECT_URI,
        "code_verifier": state_data["code_verifier"],
    }
    if device_id:
        data["device_id"] = device_id

    try:
        response = requests.post(
            "https://id.vk.ru/oauth2/auth",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        app.logger.exception("VK OAuth token exchange request failed")
        return render_oauth_error(str(error))

    try:
        result = response.json()
    except ValueError:
        app.logger.error("VK OAuth token exchange returned non-JSON response")
        return render_oauth_error("VK вернул не-JSON ответ при обмене code.")

    if "error" in result:
        error_text = result.get("error_description") or result.get("error") or "unknown_error"
        app.logger.error("VK OAuth token exchange error: %s", error_text)
        return render_oauth_error(error_text)

    app.logger.info("VK OAuth token exchange completed")
    return render_vk_token_debug_page(result)


@app.route("/vk", methods=["POST"])
def vk_callback():
    payload = request.get_json(silent=True) or {}
    app.logger.info("VK callback payload: %s", payload)

    event_type = payload.get("type")

    if event_type == "confirmation":
        return Response(VK_CONFIRMATION_RESPONSE, mimetype="text/plain")

    if event_type == "message_new":
        message = payload.get("object", {}).get("message", {})
        event_key = get_event_key(payload, message)
        if event_key and not mark_event_processed(event_key):
            app.logger.info("VK duplicate event skipped: %s", event_key)
            return "ok"

        peer_id = message.get("peer_id")
        sender_id = message.get("from_id", peer_id)
        text = message.get("text", "")

        if peer_id:
            is_first_message = get_message_count(peer_id) == 0
            if is_first_message:
                create_lead(peer_id)

            add_message(peer_id, "user", text)

            admin_reply = handle_admin_command(sender_id, text.strip())
            if admin_reply:
                reply_peer_id = (
                    sender_id
                    if text.strip().startswith(
                        (
                            "/post",
                            "/product",
                            "/publish",
                            "/create_product",
                            "/photo",
                            "/vk_market_test",
                            "/vk_auth_link",
                            "/vk_token_debug",
                        )
                    )
                    else peer_id
                )
                admin_replies = admin_reply if isinstance(admin_reply, list) else [admin_reply]
                for reply_part in admin_replies:
                    if isinstance(reply_part, dict) and reply_part.get("type") == "photo":
                        if send_vk_photo_message(reply_peer_id, reply_part["path"]):
                            add_message(peer_id, "assistant", f"photo:{reply_part['label']}")
                    else:
                        message_text = reply_part.get("text") if isinstance(reply_part, dict) else reply_part
                        if send_vk_message(reply_peer_id, message_text):
                            add_message(peer_id, "assistant", message_text)
            elif is_first_message:
                if send_vk_message(peer_id, AUTO_REPLY_TEXT):
                    add_message(peer_id, "assistant", AUTO_REPLY_TEXT)
            else:
                if is_qualified_message(text):
                    update_lead_stage(peer_id, "qualified")

                history = get_recent_messages(peer_id, limit=20)
                reply = generate_reply(text, history=history)
                if reply:
                    if send_vk_message(peer_id, reply):
                        add_message(peer_id, "assistant", reply)
                        if get_lead_stage(peer_id) == "qualified" and is_tour_offer(reply):
                            update_lead_stage(peer_id, "offer_sent")
                else:
                    app.logger.error("No GPT reply generated for peer_id=%s", peer_id)
        else:
            app.logger.warning("VK message_new without peer_id: %s", payload)

        return "ok"

    return "ok"


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
