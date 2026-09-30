# 防断片钩子

压缩前把最近 30 条原文对话存到 `~/.claude/compact-memory/last_context.md`，压缩后自动读回上下文。

## 安装（在跑 Prism 的那台机器上）

1. 把两个脚本放到 `~/.claude/hooks/`：
   ```
   mkdir -p ~/.claude/hooks
   cp pre_compact_save.py post_compact_restore.py ~/.claude/hooks/
   ```
2. 把 `settings-snippet.json` 里的 `hooks` 合并进 `~/.claude/settings.json`（已有 `hooks` 就把两项加进去，别整个覆盖）。
3. 重启 Claude Code（Prism 里的 tmux 会话）。

## 验证

手动打一次 `/compact`，看 `~/.claude/compact-memory/last_context.md` 有没有生成；压缩完问小克"刚才我们在聊什么"。

## 调整

`pre_compact_save.py` 顶部：`KEEP` 是保留条数，`MAX_CHARS` 是单条最长字数。
