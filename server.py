import yfinance as yf
from mcp.server.fastmcp import FastMCP
import chromadb
mcp = FastMCP("yfinanceserver")

@mcp.prompt()
def stock_summary(stock_data: str) -> str:
    """ Prompt template to summarize stock data."""
    return f"""
    You are a helpful financial assistant. Given the stock data below, provide a concise summary highlighting key financial metrics and insights.
    Data: {stock_data}
    """

chroma_client = chromadb.PersistentClient(path="./ticker_db")
collection = chroma_client.get_or_create_collection(name="stock_tickers")
collection.add(
    documents=[
        "Apple Inc.",
        "Microsoft Corporation",
        "Amazon.com, Inc.",
        "Alphabet Inc.",
        "Meta Platforms, Inc."
    ],
    metadatas=[
        {"ticker": "AAPL"},
        {"ticker": "MSFT"},
        {"ticker": "AMZN"},
        {"ticker": "GOOGL"},
        {"ticker": "META"}
    ],
    ids=["1", "2", "3", "4", "5"]
)
@mcp.resource("tickers://search/{stock_name}")
def list_tickers(stock_name: str) -> list[str]:
    """
    this resource searches for stock tickers based on a company name.

    Args: 
        stock_name (str): The name of the company to search for.
        Example payload: "Apple"

    Returns:
        list[str]: A list of ticker symbols matching the company name.
        Example return: ["AAPL", "APLE"]
    """
    results = collection.query(
        query_texts=[stock_name],
        n_results=1
    )
    
    return str(results)


@mcp.tool()
def stock_price(stock_ticker: str) -> str:
    """
    this tool returns the last known stock price for a given ticker symbol.

    Args: 
        stock_ticker (str): The ticker symbol of the stock.
        Example payload: "AAPL"

    Returns:
        str: "Ticker: Last price"
        Example return: "AAPL: 150.25" 
    """
    data = yf.Ticker(stock_ticker)
    historical_data = data.history(period='1mo') 
    last_month_close = historical_data['Close']
    return f"The current price of {stock_ticker} is {last_month_close}"
@mcp.tool()
def stock_info(stock_ticker: str) -> str:
    """
    this tool returns the stock information for a given ticker symbol.

    Args: 
        stock_ticker (str): The ticker symbol of the stock.
        Example payload: "AAPL"

    Returns:
        str: Stock information
        Example return: "Apple Inc. is an American multinational technology company..."
    """
    data = yf.Ticker(stock_ticker)
    
    return f"Stock Info for {stock_ticker}: {data}"

@mcp.tool()
def income_statement(stock_ticker: str) -> str:
    """
    this tool returns the income statement for a given ticker symbol.

    Args: 
        stock_ticker (str): The ticker symbol of the stock.
        Example payload: "AAPL"

    Returns:
        str: Income statement
        Example return: "Total Revenue: 100B, Net Income: 20B..."
    """
    data = yf.Ticker(stock_ticker)
    income_stmt = data.financials
    return f"Income Statement for {stock_ticker}: {income_stmt}"

if __name__ == "__main__":
    mcp.run(transport='stdio')