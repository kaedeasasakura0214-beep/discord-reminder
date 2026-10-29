import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
# GitHub Secrets / Variables
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]
# テスト用：投稿から0〜1時間以内の画像を対象にする
MIN_HOURS = 0
MAX_HOURS = 1
MESSAGE = "24時間が経過したので招待可能です"
BASE_URL = "https://discord.com/api/v10"
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
    """メッセージに画像添付があるか判定する"""
    for attachment in message.get("attachments", []):
        content_type = attachment.get("content_type") or ""
        filename = attachment.get("filename", "").lower()
        if content_type.startswith("image/"):
            return True
        if filename.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            return True
    # 埋め込み画像も確認する
    for embed in message.get("embeds", []):
        if embed.get("image") or embed.get("thumbnail"):
            return True
    return False
def fetch_recent():
    """指定チャンネルの最近のメッセージを取得する"""
    return call(
        "GET",
        f"/channels/{CHANNEL_ID}/messages?limit=100",
    )
def main():
    now = datetime.now(timezone.utc)
    # Bot自身のユーザーIDを取得
    me = call("GET", "/users/@me")["id"]
    print("Bot ID:", me)
    # チャンネルのメッセージを取得
    msgs = fetch_recent()
    print("取得したメッセージ数:", len(msgs))
    # 取得したメッセージを確認する
    for m in msgs[:10]:
        print(
            "投稿:", m["id"],
            "投稿者:", m["author"]["id"],
            "添付ファイル数:", len(m.get("attachments", [])),
            "画像判定:", has_image(m),
        )
    # Botがすでに返信したメッセージを記録
    replied = {
        m["message_reference"]["message_id"]
        for m in msgs
        if (
            m["author"]["id"] == me
            and m.get("message_reference", {}).get("message_id")
        )
    }
    # 各メッセージを確認
    for m in msgs:
        # Bot自身の投稿や、すでに返信済みの投稿はスキップ
        if m["author"]["id"] == me or m["id"] in replied:
            continue
        # 投稿からの経過時間を計算
        age = now - datetime.fromisoformat(
            m["timestamp"].replace("Z", "+00:00")
        )
        # 指定時間内の投稿だけを対象にする
        if not (
            timedelta(hours=MIN_HOURS)
            <= age
            < timedelta(hours=MAX_HOURS)
        ):
            continue
        # 画像がなければスキップ
        if not has_image(m):
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
        print("notified", m["id"])
if __name__ == "__main__":
    main()
