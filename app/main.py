"""FastAPI application. Run with: uvicorn app.main:app"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import groq
from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded

from app import data
from app.agent import ask, build_agent
from app.config import LOCALHOST_ORIGIN_REGEX, settings
from app.security import limiter, require_api_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("stock_ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.checkpoint_db).parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db) as checkpointer:
        if settings.groq_api_key:
            app.state.agent = build_agent(checkpointer)
        else:
            app.state.agent = None
            logger.warning("GROQ_API_KEY is not set: /api/v1/chat will return 503.")
        yield


app = FastAPI(
    title="Stock AI API",
    version="1.0.0",
    description="Stock data, screeners and an LLM stock-analysis agent. Data from Yahoo Finance.",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=LOCALHOST_ORIGIN_REGEX,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
    expose_headers=["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    max_age=600,
)


# ---------- error handling ----------

def _error(status_code: int, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": message}, headers=headers)


@app.exception_handler(RateLimitExceeded)
async def rate_limited(request: Request, exc: RateLimitExceeded):
    response = _error(429, f"Rate limit exceeded: {exc.detail}. Slow down and retry later.")
    return request.app.state.limiter._inject_headers(response, request.state.view_rate_limit)


@app.exception_handler(data.NotFoundError)
async def not_found(request: Request, exc: data.NotFoundError):
    return _error(404, str(exc))


@app.exception_handler(data.UpstreamError)
async def upstream_failed(request: Request, exc: data.UpstreamError):
    return _error(503, str(exc), {"Retry-After": "30"})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _error(500, "Internal server error.")


# ---------- schemas ----------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000, examples=["How did NVDA do this month?"])
    thread_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]{8,64}$",
        description="Conversation id. Omit to start a new conversation; send back the returned id to continue it.",
    )


class ChatResponse(BaseModel):
    reply: str
    thread_id: str
    tools_used: list[str]


# ---------- routes ----------

@app.get("/", include_in_schema=False)
def root():
    return {"name": "Stock AI API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


api = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])


@api.post("/chat", response_model=ChatResponse, tags=["agent"])
@limiter.limit(settings.rate_limit_chat)
async def chat(request: Request, response: Response, body: ChatRequest):
    """Ask the stock-analysis agent a question. Conversation memory is kept per `thread_id`."""
    agent = request.app.state.agent
    if agent is None:
        return _error(503, "Chat is not configured on this server (missing GROQ_API_KEY).")

    thread_id = body.thread_id or uuid.uuid4().hex
    try:
        reply, tools_used = await ask(agent, body.message, thread_id)
    except asyncio.TimeoutError:
        return _error(504, "The agent took too long to answer. Try a narrower question.")
    except groq.RateLimitError:
        return _error(503, "The language model is rate limited right now. Try again in a minute.", {"Retry-After": "60"})
    except groq.APIError:
        logger.exception("Groq API error")
        return _error(502, "The language model provider returned an error. Try again.")
    return ChatResponse(reply=reply, thread_id=thread_id, tools_used=tools_used)


@api.get("/search", tags=["data"])
@limiter.limit(settings.rate_limit_data)
def search(
    request: Request,
    response: Response,
    q: str = Query(min_length=1, max_length=100, description="Company name or partial ticker"),
    limit: int = Query(5, ge=1, le=10),
):
    """Find ticker symbols by company name."""
    return {"query": q, "results": data.search_tickers(q, limit)}


@api.get("/stocks/{ticker}/price", tags=["data"])
@limiter.limit(settings.rate_limit_data)
def stock_price(
    request: Request,
    response: Response,
    ticker: str,
    period: Literal["5d", "1mo", "3mo", "6mo", "1y", "5y"] = "1mo",
):
    """Latest close, daily change and daily closing history over `period`."""
    return data.get_price(ticker, period)


@api.get("/stocks/{ticker}/info", tags=["data"])
@limiter.limit(settings.rate_limit_data)
def stock_info(request: Request, response: Response, ticker: str):
    """Company profile and key valuation / financial metrics."""
    return data.get_info(ticker)


@api.get("/stocks/{ticker}/income-statement", tags=["data"])
@limiter.limit(settings.rate_limit_data)
def income_statement(
    request: Request,
    response: Response,
    ticker: str,
    frequency: Literal["yearly", "quarterly"] = "yearly",
):
    """Full income statement, keyed by period end date then line item."""
    return data.get_income_statement(ticker, frequency)


@api.get("/screener", tags=["data"])
def screener_types():
    """List available predefined screens."""
    return {"screen_types": list(data.SCREEN_TYPES)}


@api.get("/screener/{screen_type}", tags=["data"])
@limiter.limit(settings.rate_limit_data)
def screener(
    request: Request,
    response: Response,
    screen_type: str,
    offset: int = Query(0, ge=0, le=1000),
    count: int = Query(10, ge=1, le=50),
):
    """Run a Yahoo Finance predefined screen (e.g. day_gainers, most_actives)."""
    return data.screen(screen_type, offset, count)


app.include_router(api)
