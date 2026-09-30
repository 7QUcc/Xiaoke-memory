#!/usr/bin/env python3
# 压缩前：把最近的原文对话存下来，压缩后再喂回去，防止断片
import json
import os
import sys
from datetime import datetime

BUDGET_CHARS = 15000  # 总共保留多少字（从最新往前数）
MAX_CHARS = 2000      # 单条消息最多保留多少字
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
            msgs.append((e["type"], parse_time(e.get("timestamp", "")), text))

    # 从最新往前取，直到用完字数
    kept, used = [], 0
    for m in reversed(msgs):
        if len(kept) >= MIN_KEEP and used + len(m[2]) > BUDGET_CHARS:
            break
        kept.append(m)
        used += len(m[2])
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
