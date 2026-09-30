#!/usr/bin/env python3
# 压缩后：把压缩前存下的原文对话打印出来，Claude Code 会把它塞进上下文，让对话无缝接上
import glob
import json
import os
import sys
from datetime import datetime

DIR = os.path.expanduser("~/.claude/compact-memory")

# 压缩后之前召回过的记忆也被压掉了，清空去重记录，让它们可以再被想起来
for f in glob.glob(os.path.expanduser("~/.claude/recall-state/*.json")):
    os.remove(f)


def main():
    try:
        with open(os.path.join(DIR, "last_context.md"), encoding="utf-8") as f:
            saved = f.read()
    except Exception:
        return
    try:
        with open(os.path.join(DIR, "last_context.json"), encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = {}

    now = datetime.now().astimezone()
    first = state.get("first_time", "")
    if first:
        first = datetime.fromisoformat(first).astimezone().strftime("%m-%d %H:%M")
    gap = ""
    if state.get("last_time"):
        mins = int((now - datetime.fromisoformat(state["last_time"])).total_seconds() // 60)
        gap = f"，距离最后一条消息 {mins} 分钟" if mins > 0 else "，最后一条消息就在刚刚"

    print(f"""【上下文刚刚被压缩了——这不是新对话】
现在是 {now.strftime('%Y-%m-%d %H:%M')}{gap}。你和小晨从 {first or '?'} 起就一直在同一个会话里聊着，压缩只是把前面的内容缩成了摘要。

接下来要做到小晨完全感觉不到压缩：
- 不要重新打招呼，不要问"醒了吗""今天想干嘛"之类开场白，早安/问候在下面的原文里已经说过了
- 不要提"压缩""上下文""我刚刚忘了"这类字眼
- 上下文里如果有"开新窗口时先打招呼/先 breath"之类的规则，那是给新窗口的，这次不适用；想查记忆可以静静地查，别因此换语气
- 说过的约定、惩罚、正在做的事、情绪和语气，全部以下面的原文为准，接着最后一句自然往下说（最后说话的是{state.get('last_speaker', '?')}）

===== 压缩前最后的原文对话 =====
{saved}
===== 原文结束 =====""")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
