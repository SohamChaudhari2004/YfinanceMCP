# Stock AI API: Integration Guide

How to call the Stock AI API from a website, a backend or a script.

- **Base URL**: `https://<your-service>.onrender.com` (shown on the Render dashboard). Locally: `http://localhost:8000`.
- **Format**: JSON in, JSON out. All API routes are under `/api/v1`.
- **Interactive docs**: `<base URL>/docs`. Click **Authorize** and paste your key to try requests in the browser.

---

## 1. Authentication

Every `/api/v1/*` request must send the API key in a header:

```
X-API-Key: <your key>
```

The key is the `API_KEYS` value in the Render **Environment** tab. Several comma-separated keys can be active at once, which lets you rotate a key without downtime: add the new key, update clients, then remove the old one.

A missing or wrong key returns `401`. `/health` needs no key.

> **Security note on browser use.** Anything shipped to a browser, including a key in your frontend JavaScript or a `NEXT_PUBLIC_*` variable, can be read by anyone who opens dev tools. CORS only stops *other websites* from calling the API from a browser. It does not stop curl or scripts.
>
> - **Recommended:** call the API from your server side (a Next.js route handler, a serverless function, your backend) and keep the key there. See [section 6](#6-recommended-proxy-through-your-own-backend).
> - **Acceptable for a portfolio demo:** call it directly from the browser and accept that the key is public. The rate limits cap the damage. If the key is abused, rotate it.

## 2. CORS

Browsers may call the API only from:

- `https://sohamchaudhari.in`
- `http://localhost:<any port>` and `http://127.0.0.1:<any port>` (also `https`)

Any other origin gets no CORS headers, so the browser blocks the response. `https://www.sohamchaudhari.in` is a different origin. If your site is also served on `www`, add it to `CORS_ORIGINS` on Render (comma-separated), e.g. `https://sohamchaudhari.in,https://www.sohamchaudhari.in`.

Server-to-server calls are not affected by CORS.

## 3. Rate limits

Limits apply per client IP address:

| Endpoint | Default limit |
|---|---|
| `POST /api/v1/chat` | 10 per minute and 200 per day |
| Each data endpoint | 60 per minute |

Every limited response carries these headers (readable from browser JS):

| Header | Meaning |
|---|---|
| `X-RateLimit-Limit` | Allowed requests in the window |
| `X-RateLimit-Remaining` | Requests left |
| `X-RateLimit-Reset` | Unix time when the window resets |
| `Retry-After` | Seconds to wait (on `429` only) |

Over the limit you get `429 {"detail": "Rate limit exceeded: ..."}`. Wait `Retry-After` seconds before retrying.

If you proxy through your own backend, all users share your server's IP, so they share one quota. In that case raise `RATE_LIMIT_CHAT` on Render and rate-limit per user in your backend.

## 4. Endpoints

### `POST /api/v1/chat`: ask the agent

The agent looks up live data itself (ticker search, prices, company info, income statements, screeners) and answers in Markdown.

Request:

```json
{
  "message": "What is Nvidia trading at and what is its P/E?",
  "thread_id": "optional-conversation-id"
}
```

| Field | Rules |
|---|---|
| `message` | Required, 1 to 2000 characters |
| `thread_id` | Optional, 8 to 64 characters of `A-Z a-z 0-9 _ -`. Omit it to start a new conversation |

Response `200`:

```json
{
  "reply": "**NVIDIA Corp. (NVDA)**\n\n| Metric | Value |\n|---|---|\n| Last close | $234.74 |\n| Trailing P/E | 29.64 |",
  "thread_id": "f6b7a55a55e148ef9eb6205db99dc1a4",
  "tools_used": ["search_ticker", "get_stock_price", "get_stock_info"]
}
```

- `reply` is **Markdown** (tables, bold, lists). Render it with a Markdown component such as `react-markdown` with `remark-gfm` for tables.
- **Conversation memory**: send the returned `thread_id` with the next message so the agent remembers context ("And its revenue trend?"). Store it per chat session, for example in `sessionStorage`. Anyone who knows a `thread_id` can continue that conversation, so let the server generate it, or use a random UUID.
- Memory resets when the server restarts or redeploys (Render free plan). Only the last ~30 messages of a thread are kept.
- Typical latency is 3 to 15 seconds. Show a loading state, and use a client timeout of at least 100 seconds.

### `GET /api/v1/search?q={name}&limit={1-10}`

```json
{
  "query": "reliance",
  "results": [
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries Limited", "exchange": "NSE", "type": "EQUITY"},
    {"symbol": "RS", "name": "Reliance, Inc.", "exchange": "NYSE", "type": "EQUITY"}
  ]
}
```

### `GET /api/v1/stocks/{ticker}/price?period={5d|1mo|3mo|6mo|1y|5y}`

`period` defaults to `1mo`. Tickers are case-insensitive. Non-US tickers use Yahoo suffixes: `RELIANCE.NS` (NSE), `TCS.BO` (BSE), `BRK-B`, `^GSPC` (index).

```json
{
  "symbol": "AAPL",
  "currency": "USD",
  "price": 333.35,
  "previous_close": 330.32,
  "change": 3.03,
  "change_percent": 0.92,
  "as_of": "2026-10-02T00:00:00-04:00",
  "period": "5d",
  "history": [
    {"date": "2026-09-28", "close": 338.4},
    {"date": "2026-10-02", "close": 333.35}
  ]
}
```

`history` is daily closes, ready for a line chart.

### `GET /api/v1/stocks/{ticker}/info`

Company profile and metrics. Fields Yahoo doesn't have for that ticker are omitted, so treat every field as optional.

```json
{
  "symbol": "MSFT",
  "longName": "Microsoft Corporation",
  "sector": "Technology",
  "industry": "Software - Infrastructure",
  "currency": "USD",
  "currentPrice": 512.3,
  "marketCap": 3810000000000,
  "trailingPE": 37.1,
  "forwardPE": 32.4,
  "dividendYield": 0.65,
  "fiftyTwoWeekLow": 344.79,
  "fiftyTwoWeekHigh": 555.45,
  "averageAnalystRating": "1.4 - Strong Buy",
  "longBusinessSummary": "Microsoft Corporation develops and supports software..."
}
```

Possible fields: `symbol, longName, shortName, quoteType, exchange, currency, sector, industry, country, website, fullTimeEmployees, currentPrice, previousClose, open, dayLow, dayHigh, fiftyTwoWeekLow, fiftyTwoWeekHigh, marketCap, enterpriseValue, trailingPE, forwardPE, priceToBook, trailingEps, forwardEps, dividendYield, beta, profitMargins, revenueGrowth, earningsGrowth, totalRevenue, totalDebt, totalCash, averageAnalystRating, recommendationKey, targetMeanPrice, longBusinessSummary`.

### `GET /api/v1/stocks/{ticker}/income-statement?frequency={yearly|quarterly}`

Keyed by period end date, then line item. Values are in the reporting currency. Missing values are `null`.

```json
{
  "symbol": "GOOGL",
  "frequency": "yearly",
  "periods": {
    "2025-12-31": {"Total Revenue": 402836000000.0, "Net Income": 118500000000.0, "Diluted EPS": 9.6},
    "2024-12-31": {"Total Revenue": 350018000000.0, "Net Income": 100118000000.0, "Diluted EPS": 8.04}
  }
}
```

### `GET /api/v1/screener`

```json
{"screen_types": ["aggressive_small_caps", "conservative_foreign_funds", "day_gainers", "day_losers", "growth_technology_stocks", "high_yield_bond", "most_actives", "most_shorted_stocks", "portfolio_anchors", "small_cap_gainers", "solid_large_growth_funds", "solid_midcap_growth_funds", "top_mutual_funds", "undervalued_growth_stocks", "undervalued_large_caps"]}
```

### `GET /api/v1/screener/{screen_type}?offset={0-1000}&count={1-50}`

`count` defaults to 10. Page with `offset` (0, 10, 20...). `total` is the number of matches.

```json
{
  "screen_type": "day_gainers",
  "offset": 0,
  "total": 211,
  "results": [
    {
      "symbol": "VSH",
      "shortName": "Vishay Intertechnology, Inc.",
      "exchange": "NYQ",
      "regularMarketPrice": 38.72,
      "regularMarketChangePercent": 12.97,
      "regularMarketVolume": 4523139,
      "marketCap": 5938841600
    }
  ]
}
```

### `GET /health`

`{"status": "ok"}`. No key, no rate limit. Use it for uptime checks, or to wake the free-plan service before the user needs it.

## 5. Errors

Errors always look like `{"detail": "<message>"}` (validation errors: `detail` is a list).

| Status | When | What to do |
|---|---|---|
| `400` / `422` | Invalid input (empty message, bad `period`, bad `thread_id`) | Fix the request |
| `401` | Missing or wrong `X-API-Key` | Check the key |
| `404` | Unknown ticker or screen type | Show "not found" |
| `429` | Rate limit hit | Wait `Retry-After` seconds |
| `500` | Server bug | Retry later; check Render logs |
| `502` | LLM provider error | Retry |
| `503` | Yahoo Finance or Groq rate limited / down, or chat not configured | Wait `Retry-After`, then retry |
| `504` | Agent took longer than 90 s | Ask a narrower question |

Data is cached server-side (prices 2 min, screens 5 min, info 1 h, financials 6 h), so polling faster than that returns the same numbers.

## 6. Recommended: proxy through your own backend

This keeps the key secret. Example as a Next.js App Router route handler (`app/api/stock-chat/route.ts`):

```ts
export async function POST(req: Request) {
  const body = await req.json();
  const upstream = await fetch(`${process.env.STOCK_API_URL}/api/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": process.env.STOCK_API_KEY!, // server-only env var, NOT NEXT_PUBLIC_
    },
    body: JSON.stringify({ message: body.message, thread_id: body.thread_id }),
    signal: AbortSignal.timeout(100_000),
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
```

Your frontend then calls `/api/stock-chat` on your own domain, with no key and no CORS issue. The same pattern works for any other endpoint, or in Express, Cloudflare Workers, Vercel functions and so on.

## 7. Calling directly from the browser

A small client (TypeScript or JavaScript):

```ts
const API_URL = "https://<your-service>.onrender.com";
const API_KEY = "<key>"; // visible to anyone; see the security note in section 1

export class StockApiError extends Error {
  constructor(public status: number, message: string, public retryAfter?: number) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY, ...init.headers },
    signal: init.signal ?? AbortSignal.timeout(100_000),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Invalid request";
    throw new StockApiError(res.status, detail, Number(res.headers.get("Retry-After")) || undefined);
  }
  return data as T;
}

export const stockApi = {
  chat: (message: string, thread_id?: string) =>
    request<{ reply: string; thread_id: string; tools_used: string[] }>("/api/v1/chat", {
      method: "POST",
      body: JSON.stringify({ message, thread_id }),
    }),
  search: (q: string) => request(`/api/v1/search?q=${encodeURIComponent(q)}`),
  price: (ticker: string, period = "1mo") =>
    request(`/api/v1/stocks/${encodeURIComponent(ticker)}/price?period=${period}`),
  info: (ticker: string) => request(`/api/v1/stocks/${encodeURIComponent(ticker)}/info`),
  incomeStatement: (ticker: string, frequency = "yearly") =>
    request(`/api/v1/stocks/${encodeURIComponent(ticker)}/income-statement?frequency=${frequency}`),
  screener: (type: string, offset = 0, count = 10) =>
    request(`/api/v1/screener/${type}?offset=${offset}&count=${count}`),
};
```

A minimal React chat component that keeps the conversation going:

```tsx
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { stockApi, StockApiError } from "./stockApi";

type Msg = { role: "user" | "assistant"; text: string };

export function StockChat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | undefined>(
    () => sessionStorage.getItem("stock-thread") ?? undefined,
  );

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setLoading(true);
    try {
      const res = await stockApi.chat(text, threadId);
      setThreadId(res.thread_id);
      sessionStorage.setItem("stock-thread", res.thread_id);
      setMessages((m) => [...m, { role: "assistant", text: res.reply }]);
    } catch (e) {
      const msg =
        e instanceof StockApiError && e.status === 429
          ? `Too many requests. Try again in ${e.retryAfter ?? 60}s.`
          : "Something went wrong. Please try again.";
      setMessages((m) => [...m, { role: "assistant", text: msg }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      {messages.map((m, i) => (
        <div key={i} className={m.role}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
        </div>
      ))}
      {loading && <p>Analyzing…</p>}
      <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
      <button onClick={send} disabled={loading}>Send</button>
    </div>
  );
}
```

To start a fresh conversation, clear `stock-thread` from `sessionStorage` and reset `threadId`.

**Cold starts:** the Render free plan sleeps after 15 idle minutes, and the first request then takes about 30 to 60 seconds. Calling `fetch(API_URL + "/health")` when the page loads wakes it up early.

## 8. Other clients

curl:

```bash
curl -X POST https://<your-service>.onrender.com/api/v1/chat \
  -H "X-API-Key: $STOCK_API_KEY" -H "Content-Type: application/json" \
  -d '{"message": "Compare AAPL and MSFT valuation"}'

curl -H "X-API-Key: $STOCK_API_KEY" \
  "https://<your-service>.onrender.com/api/v1/stocks/RELIANCE.NS/price?period=3mo"
```

Python:

```python
import os
import requests

BASE = "https://<your-service>.onrender.com/api/v1"
session = requests.Session()
session.headers["X-API-Key"] = os.environ["STOCK_API_KEY"]

r = session.post(f"{BASE}/chat", json={"message": "Top 5 most active stocks today?"}, timeout=100)
r.raise_for_status()
answer = r.json()
print(answer["reply"])

follow_up = session.post(
    f"{BASE}/chat",
    json={"message": "Which of those has the highest volume?", "thread_id": answer["thread_id"]},
    timeout=100,
).json()
```

## 9. Disclaimer

Data comes from Yahoo Finance through `yfinance`, may be delayed, and is not guaranteed accurate. Agent answers are generated by an LLM and are not investment advice. Show a disclaimer next to the chat on your site.
