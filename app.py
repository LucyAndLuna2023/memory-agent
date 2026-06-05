#!/usr/bin/env python3
"""
MemoryAgent - Qwen Cloud AI Hackathon Track 1
Production-grade AI Agent with persistent memory, semantic retrieval,
intelligent forgetting, and context window management.
Powered by Qwen Cloud (DashScope) on Alibaba Cloud.
"""

import os, json, hashlib, hmac, sqlite3, time, math, threading, re
from datetime import datetime, timezone, timedelta
from collections import Counter
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memories.db")
API_KEY = os.environ.get("MEMORY_API_KEY", "sk-mem-agent-2026")
QWEN_KEY = os.environ.get("QWEN_API_KEY", "changeme")
QWEN_URL = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1") + "/chat/completions"

import urllib.request

def call_qwen(messages, max_tokens=1024, temperature=0.7):
    payload = json.dumps({
        "model": "qwen-max",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }).encode()
    req = urllib.request.Request(QWEN_URL, data=payload, headers={
        "Authorization": f"Bearer {QWEN_KEY}",
        "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[AI Error: {e}]"

# ═══════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    # Check if old schema needs migration
    cols = [c[1] for c in conn.execute("PRAGMA table_info(memories)").fetchall()]
    if "session_id" not in cols:
        # Drop and recreate with new schema
        conn.execute("DROP TABLE IF EXISTS sessions")
        conn.execute("DROP TABLE IF EXISTS memories")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
            session_id TEXT, collection TEXT DEFAULT 'default',
            content TEXT NOT NULL, summary TEXT,
            embedding BLOB, tags TEXT, metadata TEXT,
            importance REAL DEFAULT 1.0,
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT, created_at TEXT, updated_at TEXT,
            ttl INTEGER
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
            title TEXT, context_json TEXT,
            message_count INTEGER DEFAULT 0,
            created_at TEXT, updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_user_col ON memories(user_id, collection);
        CREATE INDEX IF NOT EXISTS idx_session ON memories(session_id);
        CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance);
        CREATE INDEX IF NOT EXISTS idx_accessed ON memories(last_accessed);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
    """)
    conn.commit(); conn.close()

# ═══════════════════════════════════════════
# AI FUNCTIONS
# ═══════════════════════════════════════════

def summarize_memory(content, existing_summary=None):
    if existing_summary:
        prompt = f"Merge this new info into the existing summary. Keep it under 100 words.\n\nExisting: {existing_summary}\n\nNew: {content}"
    else:
        prompt = f"Summarize this memory in under 80 words, capturing key facts:\n\n{content}"
    msgs = [{"role": "system", "content": "You are a memory compression engine. Output ONLY the summary, no commentary."},
            {"role": "user", "content": prompt}]
    return call_qwen(msgs, max_tokens=200, temperature=0.3)

def rate_importance(content):
    prompt = f"Rate the importance of this information on a scale of 1-10, where 10 is critical knowledge that must never be forgotten. Return ONLY the number.\n\nContent: {content}"
    msgs = [{"role": "user", "content": prompt}]
    result = call_qwen(msgs, max_tokens=10, temperature=0.1)
    try:
        return min(max(float(result.strip()), 0.1), 10.0)
    except:
        return 5.0

def decide_forgetting(memories_context):
    prompt = f"""You are a memory manager. For each memory below, decide: KEEP, WEAKEN, or FORGET.
Respond in JSON: [{{"id": "...", "action": "KEEP|WEAKEN|FORGET", "reason": "..."}}]

Memories:
{memories_context}"""
    msgs = [{"role": "system", "content": "Memory garbage collector. Output ONLY valid JSON array."},
            {"role": "user", "content": prompt}]
    result = call_qwen(msgs, max_tokens=1000, temperature=0.2)
    try:
        start = result.find("[")
        end = result.rfind("]") + 1
        return json.loads(result[start:end])
    except:
        return []

# ═══════════════════════════════════════════
# TF-IDF EMBEDDING & SEMANTIC SEARCH
# ═══════════════════════════════════════════

TOKEN_RE = re.compile(r'\w+')

def tokenize(text):
    return TOKEN_RE.findall(str(text).lower())

def tfidf_vector(doc, corpus_dfs, total_docs):
    tokens = tokenize(doc)
    if not tokens:
        return {}
    tf = Counter(tokens)
    vec = {}
    for term, freq in tf.items():
        df = corpus_dfs.get(term, 1)
        vec[term] = (freq / len(tokens)) * math.log((total_docs + 1) / (df + 1)) + 1
    return vec

def cosine_similarity(vec1, vec2):
    if not vec1 or not vec2:
        return 0.0
    all_terms = set(vec1) | set(vec2)
    dot = sum(vec1.get(t, 0) * vec2.get(t, 0) for t in all_terms)
    mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
    mag2 = math.sqrt(sum(v**2 for v in vec2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)

def build_corpus_stats(conn):
    rows = conn.execute("SELECT content FROM memories WHERE importance > 0").fetchall()
    docs = [r["content"] for r in rows]
    total = len(docs)
    dfs = {}
    for doc in docs:
        seen = set()
        for term in tokenize(doc):
            if term not in seen:
                dfs[term] = dfs.get(term, 0) + 1
                seen.add(term)
    return docs, dfs, total

# ═══════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════

def verify_api_key(req):
    key = req.headers.get("X-API-Key", "")
    return hmac.compare_digest(key, API_KEY)

# ═══════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════

@app.route("/")
def dashboard():
    return send_from_directory("static", "index.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "engine": "Qwen Cloud MemoryAgent", "version": "2.0.0"})

@app.route("/memories", methods=["POST"])
def create_memory():
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(force=True, silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400
    user_id = body.get("user_id")
    content = body.get("content")
    if not user_id or not content:
        return jsonify({"error": "user_id and content are required"}), 400

    now = datetime.now(timezone.utc).isoformat()
    mem_id = f"mem_{hashlib.sha256(f'{user_id}:{content}:{now}'.encode()).hexdigest()[:16]}"

    # AI processing
    summary = summarize_memory(content)
    importance = rate_importance(content)

    session_id = body.get("session_id")
    if session_id:
        conn = get_db()
        conn.execute("""
            INSERT INTO sessions (id, user_id, title, context_json, message_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET message_count = message_count + 1, updated_at = ?
        """, (session_id, user_id, summary[:100], "{}", now, now, now))
        conn.commit(); conn.close()

    conn = get_db()
    conn.execute("""
        INSERT INTO memories (id, user_id, session_id, collection, content, summary, tags, metadata, importance, access_count, last_accessed, created_at, updated_at, ttl)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
    """, (mem_id, user_id, session_id, body.get("collection", "default"), content, summary,
          json.dumps(body.get("tags", [])), json.dumps(body.get("metadata", {})),
          importance, now, now, now, body.get("ttl")))
    conn.commit(); conn.close()

    return jsonify({"id": mem_id, "summary": summary, "importance": round(importance, 2), "created_at": now}), 201

@app.route("/memories", methods=["GET"])
def list_memories():
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    collection = request.args.get("collection", "default")
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = int(request.args.get("offset", 0))

    conn = get_db()
    rows = conn.execute("""
        SELECT id, content, summary, tags, importance, access_count, last_accessed, created_at, ttl
        FROM memories
        WHERE user_id = ? AND collection = ? AND importance > 0
        ORDER BY importance DESC, last_accessed DESC
        LIMIT ? OFFSET ?
    """, (user_id, collection, limit, offset)).fetchall()

    now = datetime.now(timezone.utc)
    memories = []
    for r in rows:
        if r["ttl"]:
            created = datetime.fromisoformat(r["created_at"])
            if now - created > timedelta(seconds=r["ttl"]):
                conn.execute("UPDATE memories SET importance = 0 WHERE id = ?", (r["id"],))
                continue
        memories.append(dict(r))

    ids = [m["id"] for m in memories]
    if ids:
        now_str = now.isoformat()
        conn.executemany("UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                         [(now_str, mid) for mid in ids])
    conn.commit(); conn.close()

    return jsonify({"count": len(memories), "memories": memories})

@app.route("/memories/search", methods=["GET"])
def search_memories():
    """Semantic search via TF-IDF cosine similarity"""
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401
    user_id = request.args.get("user_id")
    query = request.args.get("q", "")
    if not user_id or not query:
        return jsonify({"error": "user_id and q required"}), 400

    conn = get_db()
    docs, dfs, total = build_corpus_stats(conn)
    query_vec = tfidf_vector(query, dfs, total)

    rows = conn.execute("""
        SELECT id, content, summary, importance, access_count, last_accessed
        FROM memories WHERE user_id = ? AND importance > 0
    """, (user_id,)).fetchall()

    results = []
    for r in rows:
        doc_vec = tfidf_vector(r["content"], dfs, total)
        sim = cosine_similarity(query_vec, doc_vec)
        results.append({"id": r["id"], "content": r["content"][:200], "summary": r["summary"],
                        "importance": r["importance"], "similarity": round(sim, 4),
                        "last_accessed": r["last_accessed"]})

    results.sort(key=lambda x: x["similarity"] * 0.7 + x["importance"] * 0.03, reverse=True)
    conn.close()
    return jsonify({"query": query, "results": results[:10]})

@app.route("/memories/context", methods=["GET"])
def get_context():
    """Smart context window - optimal memory set for LLM injection"""
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401
    user_id = request.args.get("user_id")
    max_tokens = int(request.args.get("max_tokens", 2000))
    query = request.args.get("q", "")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    conn = get_db()
    rows = conn.execute("SELECT * FROM memories WHERE user_id = ? AND importance > 0 ORDER BY importance DESC, last_accessed DESC", (user_id,)).fetchall()

    if query:
        docs, dfs, total = build_corpus_stats(conn)
        query_vec = tfidf_vector(query, dfs, total)
        scored = []
        for r in rows:
            doc_vec = tfidf_vector(r["content"], dfs, total)
            sim = cosine_similarity(query_vec, doc_vec)
            score = sim * 0.6 + (r["importance"] / 10.0) * 0.3 + min(r["access_count"] / 50.0, 1.0) * 0.1
            scored.append((score, dict(r)))
        scored.sort(key=lambda x: x[0], reverse=True)
    else:
        scored = [(r["importance"], dict(r)) for r in rows]

    context = []
    total_chars = 0
    for score, mem in scored:
        entry = f"[Importance: {mem['importance']:.1f}] {mem['summary'] or mem['content']}"
        if total_chars + len(entry) < max_tokens * 4:
            context.append(entry)
            total_chars += len(entry) + 2

    conn.close()
    return jsonify({"context": context, "memory_count": len(context), "estimated_tokens": total_chars // 4})

@app.route("/memories/forget", methods=["POST"])
def run_forgetting():
    """AI-driven memory garbage collection"""
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(force=True, silent=True) or {}
    user_id = body.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    conn = get_db()
    rows = conn.execute("""
        SELECT id, content, summary, importance, access_count, last_accessed, created_at
        FROM memories WHERE user_id = ? AND importance > 0
        ORDER BY last_accessed ASC LIMIT 20
    """, (user_id,)).fetchall()

    if not rows:
        conn.close()
        return jsonify({"forgotten": 0, "weakened": 0})

    ctx_lines = []
    for i, r in enumerate(rows):
        days_ago = "never"
        if r["last_accessed"]:
            delta = datetime.now(timezone.utc) - datetime.fromisoformat(r["last_accessed"])
            days_ago = f"{delta.days}d ago"
        ctx_lines.append(f"[{i}] id={r['id']} imp={r['importance']:.1f} acc={r['access_count']}x last={days_ago} | {r['content'][:100]}")

    decisions = decide_forgetting("\n".join(ctx_lines))

    forgotten = 0; weakened = 0
    for d in decisions:
        mid = d.get("id", "")
        action = d.get("action", "KEEP")
        if action == "FORGET":
            conn.execute("UPDATE memories SET importance = 0 WHERE id = ?", (mid,))
            forgotten += 1
        elif action == "WEAKEN":
            conn.execute("UPDATE memories SET importance = MAX(importance * 0.5, 0.5) WHERE id = ?", (mid,))
            weakened += 1

    # TTL-based forgetting
    now = datetime.now(timezone.utc)
    ttl_rows = conn.execute("SELECT id, created_at, ttl FROM memories WHERE importance > 0 AND ttl IS NOT NULL").fetchall()
    for r in ttl_rows:
        created = datetime.fromisoformat(r["created_at"])
        if now - created > timedelta(seconds=r["ttl"]):
            conn.execute("UPDATE memories SET importance = 0 WHERE id = ?", (r["id"],))
            forgotten += 1

    conn.commit(); conn.close()
    return jsonify({"forgotten": forgotten, "weakened": weakened, "decisions": decisions})

@app.route("/sessions", methods=["GET"])
def list_sessions():
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    conn = get_db()
    rows = conn.execute("""
        SELECT id, title, message_count, created_at, updated_at
        FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT 50
    """, (user_id,)).fetchall()
    conn.close()
    return jsonify({"sessions": [dict(r) for r in rows]})

@app.route("/stats", methods=["GET"])
def get_stats():
    if not verify_api_key(request):
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
    active = conn.execute("SELECT COUNT(*) as c FROM memories WHERE importance > 0").fetchone()["c"]
    users = conn.execute("SELECT COUNT(DISTINCT user_id) as c FROM memories").fetchone()["c"]
    sessions = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"]
    conn.close()
    return jsonify({
        "total_memories": total, "active_memories": active,
        "unique_users": users, "sessions": sessions,
        "engine": "Qwen Cloud (qwen-max)"
    })

# ═══════════════════════════════════════════
# PERIODIC IMPORTANCE DECAY
# ═══════════════════════════════════════════

def decay_importance():
    while True:
        time.sleep(3600)
        try:
            conn = get_db()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            conn.execute("""
                UPDATE memories SET importance = MAX(importance * 0.95, 0.1)
                WHERE importance > 0.2
                AND (last_accessed IS NULL OR last_accessed < ?)
            """, (cutoff,))
            conn.commit(); conn.close()
        except:
            pass

threading.Thread(target=decay_importance, daemon=True).start()

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
