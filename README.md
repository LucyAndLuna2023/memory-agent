# 🧠 MemoryAgent

> **Qwen Cloud AI Hackathon 2026 — Track 1: MemoryAgent**
> 
> Production-grade persistent memory system with intelligent forgetting, semantic search, and context window management. Powered by Qwen Cloud on Alibaba Cloud.

[![Deployed](https://img.shields.io/badge/deployed-Alibaba%20Cloud-orange)](http://8.130.179.205:5000)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 📋 Overview

MemoryAgent is an **AI-powered persistent memory layer** designed for LLM agents. It solves the fundamental problem of context window limitations by:

- 🧠 **Remembering** — Store arbitrary knowledge with AI auto-summarization
- 🔍 **Retrieving** — Semantic search using TF-IDF cosine similarity  
- 🗑️ **Forgetting** — AI-driven garbage collection with importance decay
- 📏 **Fitting** — Smart context window packing for LLM injection

### Why MemoryAgent?

LLMs lose everything between sessions. MemoryAgent gives them persistent, searchable memory — like a human's long-term memory for AI agents.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                   Clients                       │
│         (LLM Agents, Apps, ChatBots)            │
└───────────────┬─────────────────────────────────┘
                │ REST API (X-API-Key Auth)
┌───────────────▼─────────────────────────────────┐
│          MemoryAgent Flask Server               │
│  ┌───────────────────────────────────────────┐  │
│  │  POST /memories    → Create + AI Summary  │  │
│  │  GET  /memories    → List by importance   │  │
│  │  GET  /search      → Semantic retrieval   │  │
│  │  GET  /context     → LLM context window   │  │
│  │  POST /forget      → AI GC + TTL expiry   │  │
│  │  GET  /stats       → Usage dashboard      │  │
│  └───────────────────────────────────────────┘  │
│  ┌──────────────┐  ┌────────────────────────┐   │
│  │   SQLite DB  │  │  Qwen Cloud (qwen-max) │   │
│  │  Memories    │  │  Summarization         │   │
│  │  Sessions    │  │  Importance Rating      │   │
│  │  Embeddings  │  │  Memory Decisions       │   │
│  └──────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────┐
│         Alibaba Cloud ECS (乌兰察布)             │
│         ecs.e-c1m1.large / 2vCPU 2GB RAM        │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Qwen Cloud API key (DashScope)
- Alibaba Cloud ECS or any Linux server

### Install

```bash
git clone https://github.com/LucyAndLuna2023/memory-agent.git
cd memory-agent
pip install flask
```

### Configure

```bash
export QWEN_API_KEY="sk-your-key-here"
export QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export MEMORY_API_KEY="sk-mem-agent-2026"
export PORT=5000
```

### Run

```bash
python3 app.py
# → http://localhost:5000
```

### Deploy (systemd)

```bash
sudo cp memory-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now memory-agent
```

---

## 📡 API Reference

All endpoints require `X-API-Key` header for authentication.

### Create Memory
```bash
curl -X POST http://8.130.179.205:5000/memories \
  -H "X-API-Key: sk-mem-agent-2026" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice","content":"Alice lives in SF and writes Python","tags":["profile"],"ttl":86400}'
```

**Response:**
```json
{
  "id": "mem_00b2d70dae45069e",
  "summary": "Alice, a San Francisco-based Python developer.",
  "importance": 7.5,
  "created_at": "2026-06-05T09:50:50Z"
}
```

### Semantic Search
```bash
curl "http://8.130.179.205:5000/memories/search?user_id=alice&q=python+developer" \
  -H "X-API-Key: sk-mem-agent-2026"
```

### Get Context Window (for LLM injection)
```bash
curl "http://8.130.179.205:5000/memories/context?user_id=alice&q=hackathon&max_tokens=2000" \
  -H "X-API-Key: sk-mem-agent-2026"
```

**Response:** Packed memory entries sorted by relevance, optimized for token budget.

### AI Garbage Collection
```bash
curl -X POST http://8.130.179.205:5000/memories/forget \
  -H "X-API-Key: sk-mem-agent-2026" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice"}'
```

### Full API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/memories` | Create memory (AI summary + importance) |
| `GET` | `/memories` | List memories by importance |
| `GET` | `/memories/search?q=` | Semantic search |
| `GET` | `/memories/context?q=&max_tokens=` | LLM context window |
| `POST` | `/memories/forget` | AI garbage collection |
| `GET` | `/sessions` | Session history |
| `GET` | `/stats` | Usage statistics |
| `GET` | `/health` | Health check |
| `GET` | `/` | Dashboard |

---

## 🧪 Live Demo

- **Dashboard**: http://8.130.179.205:5000
- **API Key**: `sk-mem-agent-2026`

---

## 🎯 Key Features

### 1. AI-Powered Summarization
Every memory is automatically summarized by Qwen Cloud (qwen-max), reducing raw content into compact, searchable facts.

### 2. Importance Rating
Qwen Cloud rates each memory from 0.1–10.0 based on content significance. Critical information stays, trivia fades.

### 3. Semantic Search
TF-IDF vectorization + cosine similarity for finding relevant memories even with different phrasing. Combined score weights: similarity (70%) + importance (30%).

### 4. Intelligent Forgetting
Three-pronged approach:
- **AI-driven**: Qwen decides which memories to keep/weaken/forget
- **TTL-based**: Time-to-live expiration
- **Importance decay**: Unaccessed memories lose 5% importance per week

### 5. Context Window Management
Packs the most relevant memories into a token-budgeted context window for LLM injection. Prevents context overflow while ensuring critical information is included.

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **AI Engine** | Qwen Cloud (qwen-max) via DashScope |
| **Backend** | Python 3 + Flask |
| **Database** | SQLite (WAL mode, indexed) |
| **Search** | TF-IDF + Cosine Similarity |
| **Deployment** | Alibaba Cloud ECS (乌兰察布) + systemd |
| **Infrastructure** | ecs.e-c1m1.large (2vCPU / 2GB RAM / 40GB SSD) |

---

## 🏆 Hackathon Details

- **Hackathon**: Qwen Cloud Global AI Hackathon 2026
- **Track**: #1 — MemoryAgent (Long-term Agent Memory)
- **Prize Pool**: $45,000 cash + $25,000 cloud credits
- **Deadline**: July 10, 2026
- **Team**: Solo (Jason)

---

## 📄 License

MIT © 2026

