import logging
import os
import random
import re

from flask import Flask, Response, jsonify, request
import requests

from ai_manager import generate_reply
from database import (
    add_message,
    create_lead,
    get_leads,
    get_lead_status_counts,
    get_message_count,
    get_recent_messages,
    init_db,
    update_lead_stage,
    update_lead_status,
)


app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
init_db()

VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
ADMIN_ID = os.getenv("ADMIN_ID")
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


def handle_admin_command(peer_id, text):
    if not text.startswith(("/help", "/stats", "/leads", "/booked", "/lost")):
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

    booked_peer_id = parse_status_command(text, "/booked")
    if booked_peer_id is not None:
        if update_lead_status(booked_peer_id, "booked"):
            return f"Лид {booked_peer_id} переведен в booked."
        return f"Лид {booked_peer_id} не найден."

    lost_peer_id = parse_status_command(text, "/lost")
    if lost_peer_id is not None:
        if update_lead_status(lost_peer_id, "lost"):
            return f"Лид {lost_peer_id} переведен в lost."
        return f"Лид {lost_peer_id} не найден."

    return "Неверный формат команды."


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
                if send_vk_message(peer_id, admin_reply):
                    add_message(peer_id, "assistant", admin_reply)
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
                else:
                    app.logger.error("No GPT reply generated for peer_id=%s", peer_id)
        else:
            app.logger.warning("VK message_new without peer_id: %s", payload)

        return "ok"

    return "ok"


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
