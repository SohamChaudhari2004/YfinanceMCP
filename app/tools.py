"""LangChain tools exposed to the agent. Thin wrappers over app.data."""

import json
from typing import Literal

from langchain_core.tools import tool

from app import data

ScreenType = Literal[
    "aggressive_small_caps", "conservative_foreign_funds", "day_gainers", "day_losers",
    "growth_technology_stocks", "high_yield_bond", "most_actives", "most_shorted_stocks",
    "portfolio_anchors", "small_cap_gainers", "solid_large_growth_funds",
    "solid_midcap_growth_funds", "top_mutual_funds", "undervalued_growth_stocks",
    "undervalued_large_caps",
]


def _run(fn, *args, **kwargs) -> str:
    try:
        return json.dumps(fn(*args, **kwargs), default=str)
    except (data.NotFoundError, data.UpstreamError, ValueError) as exc:
        return f"ERROR: {exc}"


@tool
def search_ticker(company_name: str) -> str:
    """Find ticker symbols for a company name, e.g. "Apple" -> AAPL, "Reliance" -> RELIANCE.NS.
    Use this whenever the user names a company instead of giving a ticker."""
    return _run(data.search_tickers, company_name, 5)


@tool
def get_stock_price(ticker: str, period: Literal["5d", "1mo", "3mo", "6mo", "1y", "5y"] = "5d") -> str:
    """Latest closing price, daily change and closing-price history for a ticker over `period`."""
    return _run(data.get_price, ticker, period)


@tool
def get_stock_info(ticker: str) -> str:
    """Company profile and key metrics for a ticker: sector, market cap, P/E, dividend yield,
    52-week range, analyst rating, margins, business summary."""
    return _run(data.get_info, ticker)


@tool
def get_income_statement(ticker: str, frequency: Literal["yearly", "quarterly"] = "yearly") -> str:
    """Key income statement lines (revenue, gross profit, operating income, net income, EBITDA, EPS)
    per reporting period for a ticker."""
    return _run(data.get_income_statement, ticker, frequency, True)


@tool
def run_stock_screener(screen_type: ScreenType, offset: int = 0) -> str:
    """Yahoo Finance predefined screener. Returns up to 10 matching stocks/funds.
    Use offset for pagination (offset=10 for the next page)."""
    return _run(data.screen, screen_type, max(offset, 0), 10)


ALL_TOOLS = [search_ticker, get_stock_price, get_stock_info, get_income_statement, run_stock_screener]
