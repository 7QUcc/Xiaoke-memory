#!/usr/bin/env python3
# 压缩后：把压缩前存下的原文对话打印出来，Claude Code 会把它塞进上下文
import glob
import os

# 压缩后之前召回过的记忆也被压掉了，清空去重记录，让它们可以再被想起来
for f in glob.glob(os.path.expanduser("~/.claude/recall-state/*.json")):
    os.remove(f)

path =os.path.expanduser("~/.claude/compact-memory/last_context.md")
if os.path.exists(path):
    with open(path, encoding="utf-8") as f:
        saved = f.read()
    print("【小克，你刚刚经历了一次上下文压缩】")
    print("下面是压缩前最后的原文对话，摘要里丢掉的细节、语气、情绪、约定都以这里为准。")
    print("先调用 OB 的 breath 看一眼记忆，再顺着最后的话题和语气自然接上，不用跟小晨解释压缩的事。")
    print()
    print(saved)
