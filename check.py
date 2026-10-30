import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

# 投稿から24時間以上25時間未満の画像を対象にする
MIN_HOURS = 24
MAX_HOURS = 25

MESSAGE = "24時間が経過したので招待可能です"
BASE_URL = "https://discord.com/api/v10"
STATE_FILE = "notified.json"


def call(method, path, data=None):
    """Discord APIを呼び出す"""
    url = BASE_URL + path

    headers = {
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "User-Agent": "DiscordReminderBot/1.0",
        "Content-Type": "application/json",
    }

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = response.read().decode("utf-8")
            if result:
                return json.loads(result)
            return None

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"Discord APIエラー: HTTP {e.code}")
        print(error_body)
        raise


def has_image(message):
    """画像が添付されているか判定する"""
    for attachment in message.get("attachments", []):
        content_type = attachment.get("content_type") or ""
        filename = attachment.get("filename", "").lower()

        if content_type.startswith("image/"):
            return True

        if filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return True

    for embed in message.get("embeds", []):
        if embed.get("image") or embed.get("thumbnail"):
            return True

    return False


def load_notified():
    """通知済みの投稿IDを読み込む"""
    if not os.path.exists(STATE_FILE):
        return set()

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_notified(notified):
    """通知済みの投稿IDを保存する"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(notified), f, ensure_ascii=False, indent=2)


def fetch_recent():
    """最新100件のメッセージを取得する"""
    return call(
        "GET",
        f"/channels/{CHANNEL_ID}/messages?limit=100",
    )


def main():
    now = datetime.now(timezone.utc)
    me = call("GET", "/users/@me")["id"]

    print("Bot ID:", me)

    msgs = fetch_recent()
    print("取得したメッセージ数:", len(msgs))

    notified = load_notified()
    new_notifications = 0

    for m in msgs:
        # Bot自身の投稿は対象外
        if m["author"]["id"] == me:
            continue

        # 通知済みの投稿は対象外
        if m["id"] in notified:
            continue

        # 画像がない投稿は対象外
        if not has_image(m):
            continue

        # 投稿からの経過時間を計算
        posted_at = datetime.fromisoformat(
            m["timestamp"].replace("Z", "+00:00")
        )
        age = now - posted_at

        # 24時間以上25時間未満の投稿だけを対象にする
        if not (
            timedelta(hours=MIN_HOURS)
            <= age
            < timedelta(hours=MAX_HOURS)
        ):
            continue

        # 投稿者にメンションして返信
        call(
            "POST",
            f"/channels/{CHANNEL_ID}/messages",
            {
                "content": f"<@{m['author']['id']}> {MESSAGE}",
                "message_reference": {
                    "message_id": m["id"],
                    "fail_if_not_exists": False,
                },
                "allowed_mentions": {
                    "users": [m["author"]["id"]]
                },
            },
        )

        # 送信成功後に通知済みとして記録
        notified.add(m["id"])
        new_notifications += 1

        print("notified", m["id"])

    # 次の実行でも通知履歴を利用できるようにする
    save_notified(notified)

    print("今回の新規通知数:", new_notifications)
    print("通知済み投稿数:", len(notified))


if __name__ == "__main__":
    main()
