"""Optional MCP server exposing the same stock tools to MCP clients (Claude Desktop, IDEs).

Not used by the HTTP API. Run locally with: uv run server.py
"""

from mcp.server.fastmcp import FastMCP

from app.tools import get_income_statement, get_stock_info, get_stock_price, run_stock_screener, search_ticker

mcp = FastMCP("stock-ai")

for lc_tool in (search_ticker, get_stock_price, get_stock_info, get_income_statement, run_stock_screener):
    mcp.add_tool(lc_tool.func, name=lc_tool.name, description=lc_tool.description)


@mcp.prompt()
def stock_summary(stock_data: str) -> str:
    """Prompt template to summarize stock data."""
    return (
        "You are a helpful financial assistant. Given the stock data below, provide a concise "
        f"summary highlighting key financial metrics and insights.\nData: {stock_data}"
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
