import os

from flask import Flask, jsonify, request


app = Flask(__name__)

VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
CONFIRM_CODE = os.getenv("CONFIRM_CODE")


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
    event_type = payload.get("type")

    if event_type == "confirmation":
        return CONFIRM_CODE or ""

    if event_type == "message_new":
        return "ok"

    return "ok"


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
