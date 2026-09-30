#!/usr/bin/env python3
# 自动记忆召回：小晨每发一句话，挑出关键词去 OB 里搜，把命中的记忆塞进小克的上下文
# 挂在 UserPromptSubmit 钩子上。任何出错/超时都静默跳过，绝不耽误回复。
import json
import logging
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait

MAX_KEYWORDS = 3      # 每句话最多拿几个关键词去搜
MAX_INJECT = 3        # 每次最多塞几条记忆
SNIPPET_CHARS = 220   # 每条记忆最多保留多少字
MIN_PROMPT_CHARS = 4  # 比这短的话（嗯、好、晚安）直接跳过
TIME_BUDGET = 3.5     # 秒，超时就这次不给

SERVER_NAME = os.environ.get("OB_SERVER_NAME", "ob")
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.expanduser("~/.claude/recall-state")

# 每句都会出现、搜了也没意义的词
STOPWORDS = {
    "小克", "小晨", "崽崽", "宝宝", "老婆", "Mommy", "mommy", "Claude", "claude",
    "今天", "今晚", "现在", "刚才", "时候", "东西", "事情", "感觉", "一下", "问题",
}


def log(msg):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(os.path.join(STATE_DIR, "recall.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


# ---------- 找 OB 的地址 ----------

def find_ob_config():
    url = os.environ.get("OB_MCP_URL")
    if url:
        return url, json.loads(os.environ.get("OB_MCP_HEADERS", "{}"))

    candidates = []
    for path in (os.path.join(os.getcwd(), ".mcp.json"), os.path.expanduser("~/.claude.json")):
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            continue
        candidates.append(cfg.get("mcpServers", {}))
        for proj in cfg.get("projects", {}).values():
            candidates.append(proj.get("mcpServers", {}))

    for servers in candidates:
        s = servers.get(SERVER_NAME)
        if s and s.get("url"):
            return s["url"], s.get("headers", {})
    return None, None


# ---------- 最小 MCP 客户端（streamable HTTP） ----------

class MCP:
    def __init__(self, url, headers, timeout):
        self.url = url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **headers,
        }
        self.timeout = timeout

    def _post(self, payload):
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode(), headers=self.headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            sid = r.headers.get("Mcp-Session-Id")
            body = r.read().decode("utf-8", "replace")
            ctype = r.headers.get("Content-Type", "")
        if "id" not in payload:
            return sid, None
        if "text/event-stream" in ctype:
            for line in body.splitlines():
                if line.startswith("data:"):
                    msg = json.loads(line[5:].strip())
                    if msg.get("id") == payload["id"]:
                        return sid, msg
            return sid, None
        return sid, json.loads(body) if body.strip() else None

    def initialize(self):
        sid, _ = self._post({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "ob-recall", "version": "1"},
            },
        })
        if sid:
            self.headers["Mcp-Session-Id"] = sid
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, req_id, name, args):
        _, msg = self._post({
            "jsonrpc": "2.0", "id": req_id, "method": "tools/call",
            "params": {"name": name, "arguments": args},
        })
        content = (msg or {}).get("result", {}).get("content", [])
        text = "".join(c.get("text", "") for c in content if c.get("type") == "text")
        try:
            return json.loads(text).get("result", text)
        except Exception:
            return text


# ---------- 关键词 ----------

def clean_prompt(prompt):
    # Telegram 消息会被包成 <channel ...>正文</channel>，只要正文
    m = re.search(r"<channel[^>]*>(.*?)</channel>", prompt, re.S)
    if m:
        prompt = m.group(1)
    return re.sub(r"<[^>]+>", " ", prompt).strip()


def extract_keywords(text):
    import jieba
    import jieba.analyse
    jieba.setLogLevel(logging.WARNING)
    userdict = os.path.join(HERE, "userdict.txt")
    if os.path.exists(userdict):
        jieba.load_userdict(userdict)
    tags = jieba.analyse.extract_tags(
        text, topK=MAX_KEYWORDS * 2,
        allowPOS=("n", "nr", "nrt", "ns", "nt", "nz", "vn", "eng", "x"),
    )
    return [t for t in tags if t not in STOPWORDS and len(t) >= 2][:MAX_KEYWORDS]


# ---------- 解析 OB 返回 ----------

def parse_hits(text):
    # 剪掉"忽然想起来"的随机联想和末尾的 id 块，只留真正检索命中的
    text = text.split("=== 忽然想起来")[0].split("=== ombre:result-ids")[0]
    hits = []
    for m in re.finditer(r"\[bucket_id:([0-9a-f]+)\]\n(.*?)(?=\n---|\Z)", text, re.S):
        body = "\n".join(
            l for l in m.group(2).splitlines()
            if l.strip() and not l.startswith(("👣", "↳", "==="))
        ).strip()
        if body:
            hits.append((m.group(1), body))
    return hits


def snippet(body, keyword):
    body = re.sub(r"\s+", " ", body)
    if len(body) <= SNIPPET_CHARS:
        return body
    pos = max(body.find(keyword), 0)
    start = max(0, min(pos - SNIPPET_CHARS // 3, len(body) - SNIPPET_CHARS))
    s = body[start:start + SNIPPET_CHARS]
    return ("……" if start > 0 else "") + s + ("……" if start + SNIPPET_CHARS < len(body) else "")


# ---------- 去重 ----------

def load_seen(session_id):
    try:
        with open(os.path.join(STATE_DIR, f"{session_id}.json"), encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(session_id, seen):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, f"{session_id}.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f)


def main():
    t0 = time.time()
    data = json.load(sys.stdin)
    prompt = clean_prompt(data.get("prompt", ""))
    session_id = data.get("session_id", "default")
    if len(prompt) < MIN_PROMPT_CHARS or prompt.startswith("/"):
        return

    keywords = extract_keywords(prompt)
    if not keywords:
        return

    url, headers = find_ob_config()
    if not url:
        log(f"找不到名为 {SERVER_NAME} 的 OB 地址，跳过")
        return

    client = MCP(url, headers, timeout=TIME_BUDGET)
    client.initialize()

    pool = ThreadPoolExecutor(max_workers=len(keywords))
    futures = {
        pool.submit(client.call, i + 1, "breath_search", {
            "query": kw, "mode": "automatic", "with_ids": True, "max_results": 3,
        }): kw
        for i, kw in enumerate(keywords)
    }
    done, _ = wait(futures, timeout=max(0.1, TIME_BUDGET - (time.time() - t0)))
    pool.shutdown(wait=False, cancel_futures=True)

    seen = load_seen(session_id)
    picked = []
    for kw in keywords:  # 按关键词顺序，重要的在前
        fut = next((f for f, k in futures.items() if k == kw), None)
        if fut not in done or fut.exception():
            continue
        for bid, body in parse_hits(fut.result()):
            if bid in seen or any(bid == p[0] for p in picked):
                continue
            picked.append((bid, kw, snippet(body, kw)))
    picked = picked[:MAX_INJECT]

    log(f"关键词={keywords} 命中={len(picked)} 用时={time.time() - t0:.2f}s")
    if not picked:
        return

    seen.update(p[0] for p in picked)
    save_seen(session_id, seen)
    print("【小克自动想起来的记忆（OB召回）】相关就自然用上，不相关就当没看到，不用提到这段提示。")
    for bid, kw, text in picked:
        print(f"- （{kw}）{text} [bucket_id:{bid}]")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"出错跳过：{e!r}")
    sys.exit(0)
