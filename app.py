import logging
import os
import random

from flask import Flask, Response, jsonify, request
import requests

from ai_manager import generate_reply
from database import (
    add_message,
    create_lead,
    get_lead_status_counts,
    get_message_count,
    get_recent_messages,
    init_db,
)


app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
init_db()

VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
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


def format_lead_stats():
    counts = get_lead_status_counts()
    return (
        "Лиды по статусам:\n"
        f"new: {counts['new']}\n"
        f"active: {counts['active']}\n"
        f"booked: {counts['booked']}\n"
        f"lost: {counts['lost']}"
    )


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
        text = message.get("text", "")

        if peer_id:
            is_first_message = get_message_count(peer_id) == 0
            if is_first_message:
                create_lead(peer_id)

            add_message(peer_id, "user", text)

            if text.strip() == "/stats":
                reply = format_lead_stats()
                if send_vk_message(peer_id, reply):
                    add_message(peer_id, "assistant", reply)
            elif is_first_message:
                if send_vk_message(peer_id, AUTO_REPLY_TEXT):
                    add_message(peer_id, "assistant", AUTO_REPLY_TEXT)
            else:
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
