# 防断片 + 自动记忆召回钩子

| 文件 | 钩子 | 作用 |
|---|---|---|
| `pre_compact_save.py` | PreCompact | 压缩前把最近 20 轮（最多约 1 万字）原文对话存到 `~/.claude/compact-memory/` |
| `post_compact_restore.py` | SessionStart (compact) | 压缩后把原文读回上下文，明确告诉小克"这不是新对话、别重新打招呼"，并清空召回去重记录 |
| `check_hooks.py` | — | 装完跑一次，检查有没有别的开窗钩子在压缩后也会触发 |
| `ob_recall.py` | UserPromptSubmit | 每句话挑关键词去 OB 搜，把命中的记忆塞进上下文 |
| `userdict.txt` | — | 分词自定义词典（鸡公煲、黄蜀郎……），新词往里加 |

## 安装（在跑 Prism 的那台服务器上）

1. 装分词库：
   ```
   pip install jieba
   ```
   如果报 `install_layout` 错误，改用 `SETUPTOOLS_USE_DISTUTILS=stdlib pip install jieba`。
2. 把脚本和词典放到 `~/.claude/hooks/`：
   ```
   mkdir -p ~/.claude/hooks
   cp *.py userdict.txt ~/.claude/hooks/
   ```
3. 把 `settings-snippet.json` 里的 `hooks` 合并进 `~/.claude/settings.json`（已有 `hooks` 就把几项加进去，别整个覆盖）。
4. 在平时启动 Claude Code 的目录里跑一次 `python3 ~/.claude/hooks/check_hooks.py`。
   有 ⚠️ 的话，把那些"开新窗口时打招呼/加载开场内容"的 `SessionStart` 钩子的 `matcher` 改成 `"startup|resume"`，否则它们压缩后也会跑，小克会以为开了新窗口。
   CLAUDE.md 里如果写了"开窗先打招呼"，也改成"只在新窗口"。
5. 重启 Claude Code（Prism 里的 tmux 会话）。

## OB 地址

`ob_recall.py` 会自动从 `.mcp.json` 或 `~/.claude.json` 里找名为 `ob` 的 MCP 服务器（要求是 http 类型，有 `url`）。
名字不叫 `ob`，或者想直接指定，就设环境变量：`OB_SERVER_NAME=名字` 或 `OB_MCP_URL=http://127.0.0.1:端口/mcp`。

## 召回规则

- 少于 4 个字的话、`/` 开头的命令，不查
- jieba 挑最多 3 个关键词，**每个词单独搜**（OB 整句或多词一起搜经常搜不到）
- 用 `mode=automatic`，剪掉 OB 附带的"忽然想起来"随机联想，只要真正命中的
- 每次最多塞 3 条，每条截到 220 字（长日记会截关键词附近那段）
- 同一个窗口里召回过的不再重复给；压缩后清零
- 3.5 秒内没查完就这次不给，出错也静默跳过

## 验证 / 排查

- 发一句带具体事物的话（比如"鸡公煲"），问小克想起了什么
- 日志：`~/.claude/recall-state/recall.log`，每句一行：关键词、命中几条、用了几秒
- 压缩：聊几句后手动 `/compact`，然后接着上一句说话，小克应该直接接上、不会重新打招呼；`~/.claude/compact-memory/last_context.md` 里是存下的原文

## 调整

各脚本顶部的常量：轮数、字数、超时。Telegram 上用 reply 工具发的回复也会存成小克说的话，分段发的会合成一条。`ob_recall.py` 里的 `STOPWORDS` 是不拿去搜的词。
