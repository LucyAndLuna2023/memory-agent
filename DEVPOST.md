# MemoryAgent — Qwen Cloud AI Hackathon Submission

## Track: #1 MemoryAgent (Long-term Agent Memory)

---

## What it does

MemoryAgent gives LLM agents a **persistent, searchable long-term memory** — like a human brain's memory system. It solves the core problem: LLMs forget everything between sessions.

Every memory is:
- 🤖 **Auto-summarized** by Qwen-max into compact facts
- ⭐ **Importance-rated** (0.1–10.0) by AI judgment
- 🔍 **Semantically searchable** via TF-IDF cosine similarity
- 🗑 **Intelligently forgotten** — AI decides what to keep/weaken/delete
- 📏 **Token-budgeted** for efficient LLM context injection

## How it works

```
1. Create Memory → Qwen summarizes + rates importance
2. Store in SQLite (WAL mode, indexed)
3. Search: TF-IDF vectors + cosine similarity (70%) + importance (30%)
4. Context: Pack most relevant memories into token budget
5. Forget: Qwen reviews all memories → decides KEEP/WEAKEN/FORGET
6. Decay: Background thread reduces importance of unaccessed memories
```

## Why it matters

Current agents lose context when sessions end. With MemoryAgent, an agent can:
- Remember user preferences across days
- Recall past decisions and their context
- Build a knowledge base from conversations
- Auto-forget trivia to keep context clean

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Engine | Qwen Cloud (qwen-max) — DashScope |
| Backend | Python 3 + Flask |
| Database | SQLite (WAL mode, 4 indexes) |
| Search | Scikit-learn TF-IDF + Cosine Similarity |
| Deployment | Alibaba Cloud ECS — 乌兰察布 |
| Server | ecs.e-c1m1.large (2vCPU, 2GB RAM) |

## Live Demo

- **Video**: https://youtu.be/mUdZtSJv29E
- **API**: http://8.130.179.205:5000
- **Dashboard**: http://8.130.179.205:5000
- **GitHub**: https://github.com/LucyAndLuna2023/memory-agent
- **API Key**: `sk-mem-agent-2026`

## Demo Commands

```bash
# Health check
curl http://8.130.179.205:5000/health -H "X-API-Key: sk-mem-agent-2026"

# Create a memory (auto-summarized by Qwen!)
curl -X POST http://8.130.179.205:5000/memories \
  -H "X-API-Key: sk-mem-agent-2026" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","content":"I am a Python developer who loves open source","tags":["profile"]}'

# Search semantically
curl "http://8.130.179.205:5000/memories/search?user_id=test&q=python+developer" \
  -H "X-API-Key: sk-mem-agent-2026"

# Get context for LLM injection (token-budgeted)
curl "http://8.130.179.205:5000/memories/context?user_id=test&max_tokens=2000" \
  -H "X-API-Key: sk-mem-agent-2026"
```

