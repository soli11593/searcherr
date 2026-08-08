# Searcherr

A self-learning torrent search interface powered by [Prowlarr](https://github.com/Prowlarr/Prowlarr) Type a natural language query like *"<Series name> <encoding> <under/more> <Size in mb >"* and Searcherr parses your intent, searches across all your Prowlarr indexers, scores the results, and learns your preferences over time.
With TMDB powered homepage 

![Searcherr UI](static/logo.png)

---

## Features

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

## Quick Start (Docker) Preffered

**1. docker compose**
Create a directory then cd to that directory and create a compose.yml file and paste this
```compose.yml
services:
  searcherr:
    build:
      context: .
      dockerfile: Dockerfile
    image: soli1239/searcherr:latest
    container_name: searcherr
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
    environment:
      PROWLARR_URL: "${PROWLARR_URL}"
      PROWLARR_API_KEY: "${PROWLARR_API_KEY}"
      BEARER_TOKEN: "${BEARER_TOKEN}"
      REGEX_RULE_THRESHOLD: "${REGEX_RULE_THRESHOLD:-5}"
      EXPLORATION_FACTOR: "${EXPLORATION_FACTOR:-0.1}"
      TMDB_API_KEY: "${TMDB_API_KEY}"


```


**2. Create your `.env` file**
```bash
sudo nano .env
```

Edit `.env`:
```env
PROWLARR_URL=<your prowlarr url>
PROWLARR_API_KEY=<Your api key>

# ── Security ──────────────────────────────────────────────────────────────────
BEARER_TOKEN=changeme-secret-token #optional

# ── Tuning ────────────────────────────────────────────────────────────────────
REGEX_RULE_THRESHOLD=5
EXPLORATION_FACTOR=0.1
TMDB_API_KEY=<your Tmdb api key for homepage>
```

**3. Create required directories**

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


---

