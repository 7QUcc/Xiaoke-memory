#!/usr/bin/env python3
# 检查有没有别的 SessionStart 钩子在压缩后也会跑（会让小克以为开了新窗口、重新打招呼）
import json
import os
import re

FILES = [
    "~/.claude/settings.json",
    "~/.claude/settings.local.json",
    ".claude/settings.json",
    ".claude/settings.local.json",
]

found = False
for path in FILES:
    full = os.path.expanduser(path)
    try:
        with open(full, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        continue
    for entry in cfg.get("hooks", {}).get("SessionStart", []):
        matcher = entry.get("matcher", "")
        fires_on_compact = matcher in ("", "*") or re.search(matcher, "compact")
        for h in entry.get("hooks", []):
            cmd = h.get("command", "")
            if fires_on_compact and "post_compact_restore" not in cmd:
                found = True
                print(f"⚠️  {path}: matcher={matcher!r} 压缩后也会跑 → {cmd}")

if found:
    print("\n如果这些是\"开新窗口时打招呼/加载开场内容\"的钩子，把它们的 matcher 改成 \"startup|resume\"。")
else:
    print("✅ 没有别的 SessionStart 钩子会在压缩后触发")
