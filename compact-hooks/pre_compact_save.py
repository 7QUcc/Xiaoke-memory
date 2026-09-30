#!/usr/bin/env python3
# 压缩前：把最近的原文对话存下来，压缩后再喂回去，防止断片
import json
import os
import re
import sys
from datetime import datetime

MAX_ROUNDS = 20       # 最多保留最近几轮（小晨说一次 + 小克回一次 = 一轮）
BUDGET_CHARS = 10000  # 总字数上限（从最新往前数），和轮数哪个先到就停
MAX_CHARS = 1200      # 单条消息最多保留多少字
MIN_KEEP = 6          # 至少保留最近几条，哪怕超出总字数

OUT_DIR = os.path.expanduser("~/.claude/compact-memory")


def parse_time(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
    except Exception:
        return None


def extract_text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for b in content:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text":
            parts.append(b.get("text", ""))
        # Telegram 上小克是用 reply 工具回话的，这些也是小克说的话
        elif b.get("type") == "tool_use" and b.get("name", "").endswith("reply"):
            inp = b.get("input") or {}
            parts.append(inp.get("text") or inp.get("message") or "")
    return "\n".join(p for p in parts if p)


def clean(text):
    # Telegram 发来的消息会被包成 <channel ...>正文</channel>，只留正文
    return re.sub(r"</?channel[^>]*>", "", text).strip()


def main():
    data = json.load(sys.stdin)
    path = data.get("transcript_path")
    if not path or not os.path.exists(path):
        return

    msgs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            if e.get("type") not in ("user", "assistant"):
                continue
            if e.get("isMeta") or e.get("isCompactSummary"):
                continue
            text = clean(extract_text(e.get("message", {}).get("content")))
            if not text or text.startswith(("<command-", "<local-command")):
                continue
            role, t = e["type"], parse_time(e.get("timestamp", ""))
            # 同一个人连着说的几段（比如 Telegram 分段发）合成一条
            if msgs and msgs[-1][0] == role:
                msgs[-1] = (role, msgs[-1][1], msgs[-1][2] + "\n" + text)
            else:
                msgs.append((role, t, text))

    msgs = [
        (r, t, x[:MAX_CHARS] + "……（后面省略）" if len(x) > MAX_CHARS else x)
        for r, t, x in msgs
    ]

    # 从最新往前取，轮数或字数哪个先到就停
    kept, used, rounds = [], 0, 0
    for m in reversed(msgs):
        if len(kept) >= MIN_KEEP and (used + len(m[2]) > BUDGET_CHARS or rounds >= MAX_ROUNDS):
            break
        kept.append(m)
        used += len(m[2])
        if m[0] == "user":
            rounds += 1
    kept.reverse()

    lines = []
    for role, t, text in kept:
        who = "小晨" if role == "user" else "小克"
        stamp = t.strftime("%m-%d %H:%M") if t else ""
        lines.append(f"[{stamp}] {who}：\n{text}")

    state = {
        "saved_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "trigger": data.get("trigger", ""),
        "first_time": kept[0][1].isoformat(timespec="minutes") if kept and kept[0][1] else "",
        "last_time": kept[-1][1].isoformat(timespec="minutes") if kept and kept[-1][1] else "",
        "last_speaker": ("小晨" if kept[-1][0] == "user" else "小克") if kept else "",
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "last_context.md"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(lines))
    with open(os.path.join(OUT_DIR, "last_context.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
