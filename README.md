# Stock AI API

HTTP API for stock data, Yahoo Finance screeners and an LLM stock-analysis agent.
It combines the former `Stock_agents` (MCP stock tools) and `StockScreener` (LangGraph screener) projects into one FastAPI service.

- **Chat agent**: Groq `openai/gpt-oss-120b` with tools for ticker search, prices, company info, income statements and screeners. Conversation memory is kept per `thread_id`.
- **Data endpoints**: the same data as plain JSON, with no LLM involved (fast and cheap).
- **Protection**: `X-API-Key` header, per-IP rate limiting, CORS limited to `https://sohamchaudhari.in` and localhost.

Integration guide for frontends and clients: **[docs/INTEGRATION.md](docs/INTEGRATION.md)**.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check (no key, no rate limit) |
| POST | `/api/v1/chat` | Ask the agent |
| GET | `/api/v1/search?q=` | Find tickers by company name |
| GET | `/api/v1/stocks/{ticker}/price` | Latest price and closing history |
| GET | `/api/v1/stocks/{ticker}/info` | Company profile and key metrics |
| GET | `/api/v1/stocks/{ticker}/income-statement` | Income statement |
| GET | `/api/v1/screener` | List screen types |
| GET | `/api/v1/screener/{screen_type}` | Run a predefined screen |

Interactive docs are served at `/docs`.

## Project layout

```
app/
  main.py      FastAPI app: routes, CORS, error handling
  agent.py     LangChain agent, history trimming, per-thread locking
  tools.py     LangChain tools used by the agent
  data.py      yfinance access, validation, caching
  security.py  API-key check and rate limiter
  config.py    Settings from environment variables
server.py      Optional MCP server exposing the same tools (stdio)
tests/         API tests (no network needed)
Dockerfile, render.yaml
```

## Run locally

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11.

```bash
cp .env.example .env        # then set GROQ_API_KEY (and API_KEYS if you want the key check on)
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs. If `API_KEYS` is empty, the key check is disabled and a warning is logged.

Run tests:

```bash
uv run pytest
```

Optional MCP server for Claude Desktop or IDEs: `uv run server.py`.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `GROQ_API_KEY` | (none) | Required for `/chat`; without it `/chat` returns 503 |
| `API_KEYS` | (none) | Comma-separated accepted keys. Empty disables the check |
| `CORS_ORIGINS` | `https://sohamchaudhari.in` | Comma-separated. Localhost / 127.0.0.1 on any port is always allowed |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Any Groq chat model with tool calling |
| `RATE_LIMIT_CHAT` | `10/minute;200/day` | Per client IP, [limits syntax](https://limits.readthedocs.io/en/stable/quickstart.html#rate-limit-string-notation) |
| `RATE_LIMIT_DATA` | `60/minute` | Per client IP, per data endpoint |
| `CHECKPOINT_DB` | `data/checkpoints.sqlite` | SQLite file for conversation memory |
| `MAX_HISTORY_MESSAGES` | `30` | Older turns are dropped beyond this |
| `AGENT_TIMEOUT_SECONDS` | `90` | Chat requests over this return 504 |
| `DOCS_ENABLED` | `true` | Set `false` to hide `/docs` and `/openapi.json` |

## Deploy on Render

1. Push this folder to a GitHub repo.
2. In Render: **New > Blueprint**, pick the repo. `render.yaml` creates a Docker web service.
3. When prompted, paste your `GROQ_API_KEY`. `API_KEYS` is generated automatically; copy it from the service's **Environment** tab.
4. After the deploy, check `https://<service>.onrender.com/health`.

Without a Blueprint: **New > Web Service**, choose the repo, runtime **Docker**, health check path `/health`, and add the environment variables above by hand.

Things to know on Render:

- **Free plan sleeps** after 15 minutes idle. The first request after that takes about 30 to 60 seconds.
- **Conversation memory is lost on restart or redeploy**, because the free plan has no persistent disk. To keep it, use a paid plan, attach a disk (e.g. mounted at `/app/data`), and keep `CHECKPOINT_DB=data/checkpoints.sqlite`.
- **Run one instance with one worker.** Rate-limit counters are in memory, so scaling out would multiply the limits.
- **Yahoo Finance can rate-limit cloud IPs.** Responses are cached (prices 2 min, screens 5 min, info 1 h, financials 6 h). When Yahoo refuses, the API returns 503 with `Retry-After`.
