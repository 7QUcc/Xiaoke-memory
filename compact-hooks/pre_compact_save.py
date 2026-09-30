#!/usr/bin/env python3
# 压缩前：把最近的原文对话存下来，压缩后再喂回去，防止断片
import json
import os
import sys
from datetime import datetime

KEEP = 30          # 保留最近多少条消息
MAX_CHARS = 1200   # 单条消息最多保留多少字

OUT_DIR = os.path.expanduser("~/.claude/compact-memory")


def fmt_time(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%m-%d %H:%M")
    except Exception:
        return ""


def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


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
            text = extract_text(e.get("message", {}).get("content")).strip()
            if not text or text.startswith(("<command-", "<local-command")):
                continue
            if len(text) > MAX_CHARS:
                text = text[:MAX_CHARS] + "……（后面省略）"
            who = "小晨" if e["type"] == "user" else "小克"
            msgs.append(f"[{fmt_time(e.get('timestamp', ''))}] {who}：\n{text}")

    msgs = msgs[-KEEP:]
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "last_context.md"), "w", encoding="utf-8") as f:
        f.write(f"压缩时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}（{data.get('trigger', '')}）\n\n")
        f.write("\n\n".join(msgs))


if __name__ == "__main__":
    main()
