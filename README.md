# Searcherr

A self-learning torrent search interface powered by [Prowlarr](https://github.com/Prowlarr/Prowlarr) and a local AI model (Phi-3.5-mini). Type a natural language query like *"Re Zero season 4 AV1 under 500MB"* and Searcherr parses your intent, searches across all your Prowlarr indexers, scores the results, and learns your preferences over time.

![Searcherr UI](static/logo.png)

---

## Features

- **Natural language search** — powered by Phi-3.5-mini (GGUF) with a regex fallback if no model is present
- **Self-learning** — picks up on your codec, resolution, release group, and source preferences the more you use it
- **Auto regex rules** — automatically generates regex bonus rules for release groups you consistently choose
- **Prowlarr-powered** — searches all your configured indexers in one place
- **Filter & paginate** — filter results by codec, resolution, source, group, and file size
- **Download history** — tracks everything you've downloaded with full metadata
- **Docker-ready** — single container, no external database required (SQLite)

---

## Requirements

- [Prowlarr](https://github.com/Prowlarr/Prowlarr) running and accessible
- Docker (recommended) **or** Python 3.11+

---

## Quick Start (Docker)

**1. Clone the repo**
```bash
git clone https://github.com/soli11593/searcherr.git
cd searcherr
```

**2. Create your `.env` file**
```bash
cp .env.example .env   # or create it manually
```

Edit `.env`:
```env
PROWLARR_URL=http://your-prowlarr-host:9696
PROWLARR_API_KEY=your-api-key-here
BEARER_TOKEN=change-this-to-a-strong-secret
```

**3. Create required directories**
```bash
mkdir -p config models
```

**4. Run**
```bash
docker compose up -d
```

Open `http://localhost:8000` in your browser.

---

## Quick Start (Local / No Docker)

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Set environment variables**

Copy `.env.example` to `.env` and fill in your Prowlarr details.

**3. Run**
```bash
python starting.py
```

`starting.py` will automatically install `llama-cpp-python` (CPU-only, no compiler needed) and check for the model file before launching the server.

---

## AI Model (Optional)

Without a model the app still works using a regex-based NLP fallback. To enable full AI parsing:

1. Download `Phi-3.5-mini-instruct-Q4_K_M.gguf` (~2.4 GB) from [HuggingFace](https://huggingface.co/microsoft/Phi-3.5-mini-instruct-gguf)
2. Place it in the `models/` folder
3. Set `MODEL_FILENAME=Phi-3.5-mini-instruct-Q4_K_M.gguf` in your `.env`

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PROWLARR_URL` | `http://localhost:9696` | Prowlarr base URL |
| `PROWLARR_API_KEY` | — | Prowlarr API key (required) |
| `BEARER_TOKEN` | `changeme-secret-token` | API auth token |
| `MODEL_FILENAME` | `Phi-3.5-mini-instruct-Q4_K_M.gguf` | GGUF model filename |
| `N_CTX` | `4096` | LLM context size |
| `N_THREADS` | `4` | CPU threads for inference |
| `REGEX_RULE_THRESHOLD` | `5` | Picks before auto-generating a regex rule |
| `EXPLORATION_FACTOR` | `0.1` | `0.0` = always top-scored, `1.0` = random |

---

## Docker Hub

Pre-built image available at:
```
docker pull soli1239/searcherr:latest
```

---

## Project Structure

```
searcherr/
├── main.py              # FastAPI app entry point
├── config.py            # Config and path setup
├── starting.py          # Local dev launcher
├── db/
│   └── database.py      # SQLite schema and helpers
├── routers/
│   └── search.py        # API routes
├── services/
│   ├── nlp.py           # Intent parsing (LLM + regex fallback)
│   ├── prowlarr.py      # Prowlarr API client
│   └── scorer.py        # Result scoring engine
├── templates/
│   └── index.html       # Frontend UI
├── static/
│   └── logo.png
├── Dockerfile
└── docker-compose.yml
```

---

## License

MIT
