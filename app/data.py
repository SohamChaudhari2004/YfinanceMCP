"""Stock data access on top of yfinance.

Every public function returns plain JSON-serialisable data and raises
`NotFoundError` / `UpstreamError` instead of leaking yfinance/pandas errors.
Results are cached in-process to keep Yahoo Finance rate limiting at bay.
"""

import json
import logging
import re

import yfinance as yf
from cachetools.func import ttl_cache

logger = logging.getLogger(__name__)

TICKER_PATTERN = re.compile(r"^[A-Z0-9.\-=^]{1,15}$")
PRICE_PERIODS = ("5d", "1mo", "3mo", "6mo", "1y", "5y")
SCREEN_TYPES = tuple(sorted(yf.PREDEFINED_SCREENER_QUERIES))

INFO_FIELDS = (
    "symbol", "longName", "shortName", "quoteType", "exchange", "currency",
    "sector", "industry", "country", "website", "fullTimeEmployees",
    "currentPrice", "previousClose", "open", "dayLow", "dayHigh",
    "fiftyTwoWeekLow", "fiftyTwoWeekHigh", "marketCap", "enterpriseValue",
    "trailingPE", "forwardPE", "priceToBook", "trailingEps", "forwardEps",
    "dividendYield", "beta", "profitMargins", "revenueGrowth", "earningsGrowth",
    "totalRevenue", "totalDebt", "totalCash", "averageAnalystRating",
    "recommendationKey", "targetMeanPrice", "longBusinessSummary",
)
SCREENER_FIELDS = (
    "symbol", "shortName", "exchange", "regularMarketPrice",
    "regularMarketChangePercent", "regularMarketVolume", "marketCap", "bid", "ask",
    "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "averageAnalystRating", "dividendYield",
)
KEY_INCOME_ITEMS = (
    "Total Revenue", "Cost Of Revenue", "Gross Profit", "Research And Development",
    "Operating Expense", "Operating Income", "EBITDA", "Net Income",
    "Basic EPS", "Diluted EPS",
)


class NotFoundError(Exception):
    """The ticker / resource does not exist on Yahoo Finance."""


class UpstreamError(Exception):
    """Yahoo Finance failed or rate limited us."""


def normalize_ticker(ticker: str) -> str:
    symbol = ticker.strip().upper()
    if not TICKER_PATTERN.fullmatch(symbol):
        raise NotFoundError(f"'{ticker}' is not a valid ticker symbol.")
    return symbol


def _upstream(action: str, exc: Exception) -> UpstreamError:
    logger.warning("Yahoo Finance %s failed: %r", action, exc)
    return UpstreamError(f"Yahoo Finance is unavailable or rate limited ({action}). Try again shortly.")


@ttl_cache(maxsize=256, ttl=600)
def search_tickers(query: str, limit: int = 5) -> list[dict]:
    try:
        quotes = yf.Search(query, max_results=limit, news_count=0).quotes
    except Exception as exc:
        raise _upstream("search", exc) from exc
    return [
        {
            "symbol": q.get("symbol"),
            "name": q.get("longname") or q.get("shortname"),
            "exchange": q.get("exchDisp") or q.get("exchange"),
            "type": q.get("quoteType"),
        }
        for q in quotes
        if q.get("symbol")
    ]


@ttl_cache(maxsize=512, ttl=120)
def get_price(ticker: str, period: str = "1mo") -> dict:
    symbol = normalize_ticker(ticker)
    if period not in PRICE_PERIODS:
        raise ValueError(f"period must be one of {PRICE_PERIODS}")
    try:
        t = yf.Ticker(symbol)
        history = t.history(period=period)
        currency = t.fast_info.get("currency") if not history.empty else None
    except Exception as exc:
        raise _upstream("price", exc) from exc
    if history.empty:
        raise NotFoundError(f"No price data found for '{symbol}'.")

    closes = history["Close"].dropna()
    price = float(closes.iloc[-1])
    previous = float(closes.iloc[-2]) if len(closes) > 1 else None
    change = price - previous if previous else None
    return {
        "symbol": symbol,
        "currency": currency,
        "price": round(price, 4),
        "previous_close": round(previous, 4) if previous else None,
        "change": round(change, 4) if change is not None else None,
        "change_percent": round(change / previous * 100, 2) if change is not None else None,
        "as_of": closes.index[-1].isoformat(),
        "period": period,
        "history": [{"date": idx.date().isoformat(), "close": round(float(v), 4)} for idx, v in closes.items()],
    }


@ttl_cache(maxsize=256, ttl=3600)
def get_info(ticker: str) -> dict:
    symbol = normalize_ticker(ticker)
    try:
        info = yf.Ticker(symbol).info
    except Exception as exc:
        if "404" in str(exc) or "Not Found" in str(exc):
            raise NotFoundError(f"No company information found for '{symbol}'.") from exc
        raise _upstream("info", exc) from exc
    if not info or not (info.get("longName") or info.get("shortName")):
        raise NotFoundError(f"No company information found for '{symbol}'.")
    return {field: info.get(field) for field in INFO_FIELDS if info.get(field) is not None}


@ttl_cache(maxsize=256, ttl=6 * 3600)
def get_income_statement(ticker: str, frequency: str = "yearly", key_items_only: bool = False) -> dict:
    symbol = normalize_ticker(ticker)
    if frequency not in ("yearly", "quarterly"):
        raise ValueError("frequency must be 'yearly' or 'quarterly'")
    try:
        t = yf.Ticker(symbol)
        df = t.quarterly_income_stmt if frequency == "quarterly" else t.income_stmt
    except Exception as exc:
        raise _upstream("income statement", exc) from exc
    if df is None or df.empty:
        raise NotFoundError(f"No income statement found for '{symbol}'.")

    if key_items_only:
        df = df.loc[[item for item in KEY_INCOME_ITEMS if item in df.index]]
    df = df.copy()
    df.columns = [col.strftime("%Y-%m-%d") for col in df.columns]
    # to_json turns NaN into null; json.loads gives back plain dicts.
    return {"symbol": symbol, "frequency": frequency, "periods": json.loads(df.to_json())}


@ttl_cache(maxsize=128, ttl=300)
def screen(screen_type: str, offset: int = 0, count: int = 10) -> dict:
    predefined = yf.PREDEFINED_SCREENER_QUERIES.get(screen_type)
    if predefined is None:
        raise NotFoundError(f"Unknown screen_type '{screen_type}'. Valid: {', '.join(SCREEN_TYPES)}")
    try:
        result = yf.screen(
            predefined["query"],
            offset=offset,
            size=count,
            sortField=predefined.get("sortField"),
            sortAsc=str(predefined.get("sortType", "DESC")).upper() == "ASC",
        )
    except Exception as exc:
        raise _upstream("screener", exc) from exc
    return {
        "screen_type": screen_type,
        "offset": offset,
        "total": result.get("total"),
        "results": [
            {field: quote[field] for field in SCREENER_FIELDS if quote.get(field) is not None}
            for quote in result.get("quotes", [])
        ],
    }
