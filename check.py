import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]
MIN_HOURS = 0     # この時間が経ったら通知
MAX_HOURS = 1     # これより古い投稿は対象外(古い投稿への一斉通知を防ぐ)
MESSAGE = "24時間が経過したので招待可能です"
API = "https://discord.com/api/v10"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bot {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://github.com, 1.0)",
        },
    )
    for _ in range(3):
        try:
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read() or "null")
        except urllib.error.HTTPError as e:
            if e.code == 429:  # レート制限は待って再試行
                time.sleep(float(json.loads(e.read()).get("retry_after", 1)))
                continue
            raise
    raise RuntimeError("rate limited")


def has_image(m):
    for a in m.get("attachments", []):
        content_type = a.get("content_type") or ""
        filename = a.get("filename") or ""

        if content_type.startswith("image/"):
            return True

        if filename.lower().endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
        ):
            return True

    return False


def fetch_recent(now):
    msgs, before = [], None
    for _ in range(3):  # 最大300件さかのぼる
        path = f"/channels/{CHANNEL_ID}/messages?limit=100"
        if before:
            path += f"&before={before}"
        page = call("GET", path)
        if not page:
            break
        msgs += page
        before = page[-1]["id"]
        oldest = datetime.fromisoformat(page[-1]["timestamp"])
        if len(page) < 100 or now - oldest > timedelta(hours=MAX_HOURS):
            break
    return msgs


def main():
    now = datetime.now(timezone.utc)
    me = call("GET", "/users/@me")["id"]
    msgs = fetch_recent(now)

    # すでに返信済みの投稿ID
    replied = {
        m["message_reference"]["message_id"]
        for m in msgs
        if m["author"]["id"] == me and m.get("message_reference", {}).get("message_id")
    }

    for m in msgs:
        if m["author"]["id"] == me or m["id"] in replied:
            continue
        age = now - datetime.fromisoformat(m["timestamp"])
        if not (timedelta(hours=MIN_HOURS) <= age < timedelta(hours=MAX_HOURS)):
            continue
        if not has_image(m):
            continue
        call("POST", f"/channels/{CHANNEL_ID}/messages", {
            "content": f"<@{m['author']['id']}> {MESSAGE}",
            "message_reference": {"message_id": m["id"], "fail_if_not_exists": False},
            "allowed_mentions": {"users": [m["author"]["id"]]},
        })
        print("notified", m["id"])


if __name__ == "__main__":
    main()
