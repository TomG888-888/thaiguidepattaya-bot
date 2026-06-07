import logging
import os
import random
import re

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response, jsonify, request
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
    get_recent_messages,
    init_db,
    mark_event_processed,
    update_lead_stage,
    update_lead_status,
)
from product_manager import AVAILABLE_TOUR_KEYS, generate_product_card
from seasonal_manager import get_current_season, init_current_season, set_current_season
from tour_catalog import TOUR_CATALOG, get_public_tour, normalize_tour_key


app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
init_db()
init_current_season()

VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
ADMIN_ID = os.getenv("ADMIN_ID")
AUTO_POSTING_ENABLED = os.getenv("AUTO_POSTING_ENABLED", "false").lower() == "true"
VK_CONFIRMATION_RESPONSE = "dfe8da6d"
VK_API_VERSION = "5.199"
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
/stats
/leads
/post expert
/post sales
/post story
/product <tour_key>
/product_export <tour_key>
/product_export_all
/publish expert
/publish sales
/publish story
/season
/season set <season>
/stage <peer_id> <stage>
/booked <peer_id>
/lost <peer_id>"""


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

    route = tour.get("route")
    if route:
        lines.extend(["", "Маршрут:"])
        if isinstance(route, dict):
            stops = route.get("stops") or []
            boat_view = route.get("boat_view") or []
            if stops:
                lines.extend(["Остановки:", *[f"- {item}" for item in stops]])
            if boat_view:
                lines.extend(["Обзор с лодки:", *[f"- {item}" for item in boat_view]])
        else:
            lines.extend([f"- {item}" for item in route])

    lines.extend(["", "Что включено:", *[f"- {item}" for item in tour["included"]]])

    if tour.get("not_included"):
        lines.extend(["", "Не включено:", *[f"- {item}" for item in tour["not_included"]]])

    lines.extend(
        [
            "",
            f"Длительность: {tour['duration']}",
            f"Время в пути: {tour['travel_time']}",
            f"Отправление: {tour.get('departure') or 'уточняется при бронировании'}",
            f"Цена взрослый: {tour['price_adult']}",
            f"Цена ребёнок: {tour['price_child']}",
            "",
            "Что взять с собой:",
            *[f"- {item}" for item in tour["what_to_bring"]],
        ]
    )

    return "\n".join(lines)


def format_product_export(tour_key):
    normalized_tour_key = normalize_tour_key(tour_key)
    tour = get_public_tour(normalized_tour_key)
    if not tour:
        return f"Неизвестный тур. Используйте: {AVAILABLE_TOUR_KEYS}."

    return (
        f"Товар: {normalized_tour_key}\n\n"
        f"Название товара:\n{tour['title']}\n\n"
        f"Цена:\n{tour['price_adult']}\n\n"
        f"Описание товара:\n{format_product_export_description(tour)}"
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


def format_all_product_exports():
    exports = [format_product_export(tour_key) for tour_key in TOUR_CATALOG]
    return split_export_messages(exports)


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
            "/stats",
            "/leads",
            "/post",
            "/product",
            "/publish",
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

    if text == "/stats":
        return format_lead_stats()

    if text == "/leads":
        return format_leads()

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

    if text.startswith("/product_export"):
        parts = text.split()
        if len(parts) != 2:
            return "Неверный формат команды. Используйте /product_export samet_1d_lunch."
        return format_product_export(parts[1])

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

    result = response.json()
    if "error" in result:
        app.logger.error("VK messages.send error: %s", result["error"])
        return False

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
                    if text.strip().startswith(("/post", "/product", "/publish"))
                    else peer_id
                )
                admin_replies = admin_reply if isinstance(admin_reply, list) else [admin_reply]
                for reply_part in admin_replies:
                    if send_vk_message(reply_peer_id, reply_part):
                        add_message(peer_id, "assistant", reply_part)
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
