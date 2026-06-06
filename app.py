import logging
import os

from flask import Flask, Response, jsonify, request


app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
VK_CONFIRMATION_RESPONSE = "dfe8da6d"


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
        return "ok"

    return "ok"


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
