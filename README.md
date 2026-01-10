# YFinance Stock Agent

An MCP (Model Context Protocol) server and LangGraph agent for real-time stock market analysis using Yahoo Finance data.

## Overview

This project provides a financial assistant that can search for stock tickers, retrieve current prices, fetch detailed stock information, and analyze income statements. It consists of two main components:

1. **MCP Server** ([server.py](server.py)) - Exposes stock data tools and resources via the Model Context Protocol
2. **LangGraph Agent** ([agent.py](agent.py)) - An AI agent that uses the MCP server to answer financial queries

## Features

### MCP Server Tools

- **`stock_price(ticker)`** - Returns the last month's closing prices for a stock
- **`stock_info(ticker)`** - Fetches comprehensive stock information
- **`income_statement(ticker)`** - Retrieves financial income statement data

### MCP Server Resources

- **`tickers://search/{company_name}`** - Searches for stock tickers by company name using ChromaDB

### Prompt Templates

- **`stock_summary`** - Pre-built prompt template for summarizing stock data

## Architecture

```
┌──────────────────┐
│   User Query     │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────┐
│   LangGraph Agent        │
│   (Groq LLM + Tools)     │
└────────┬─────────────────┘
         │ MCP Protocol
         ▼
┌──────────────────────────┐
│   MCP Server             │
│   (FastMCP)              │
└────────┬─────────────────┘
         │
    ┌────┴─────┬──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌──────┐
│YFinance│ │ChromaDB│ │Tools │
└────────┘ └────────┘ └──────┘
```

## Installation

### Prerequisites

- Python 3.11
- UV package manager (recommended) or pip

### Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd Stock_agents
```

2. Install dependencies using UV:

```bash
uv sync
```

Or with pip:

```bash
pip install -e .
```

3. Create a `.env` file with your Groq API key:

```env
GROQ_API_KEY=your_groq_api_key_here
```

## Usage

### Running the MCP Server

Start the MCP server directly:

```bash
uv run mcp dev server.py
```

Or with Python:

```bash
python server.py
```

### Running the Agent

Run the interactive agent:

```bash
uv run agent.py
```

```bash
python agent.py
```

Example queries:

- "What's the current price of Apple stock?"
- "Find the ticker for Microsoft"
- "Show me the income statement for TSLA"
- "Compare the stock prices of AAPL and MSFT"

## Configuration

### Stock Ticker Database

The server initializes a ChromaDB collection with the following companies:

- Apple Inc. (AAPL)
- Microsoft Corporation (MSFT)
- Amazon.com, Inc. (AMZN)
- Alphabet Inc. (GOOGL)
- Meta Platforms, Inc. (META)

To add more companies, modify the `collection.add()` call in [server.py](server.py#L16-L32).

### LLM Configuration

The agent uses Groq's LLM service. You can modify the model in [agent.py](agent.py):

```python
llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="openai/gpt-oss-120b",  # Change model here
    temperature=0,
)
```

## Project Structure

```
Stock_agents/
├── agent.py           # LangGraph agent implementation
├── server.py          # MCP server with stock tools
├── pyproject.toml     # Project dependencies and metadata
├── README.md          # This file
├── .env               # Environment variables (not in repo)
└── ticker_db/         # ChromaDB persistent storage
    └── chroma.sqlite3
```

## Dependencies

- **yfinance** - Yahoo Finance API for stock data
- **chromadb** - Vector database for ticker search
- **fastmcp** - MCP server framework
- **langchain** - LLM framework
- **langchain-groq** - Groq LLM integration
- **langchain-mcp-adapters** - MCP client for LangChain
- **langgraph** - Agent orchestration framework

## API Reference

### Tools

#### `stock_price(stock_ticker: str) -> str`

Returns the closing prices for the last month.

**Example:**

```python
stock_price("AAPL")
# Returns: "The current price of AAPL is [Series of prices]"
```

#### `stock_info(stock_ticker: str) -> str`

Returns detailed stock information.

**Example:**

```python
stock_info("MSFT")
# Returns: "Stock Info for MSFT: <Ticker object>"
```

#### `income_statement(stock_ticker: str) -> str`

Returns the income statement data.

**Example:**

```python
income_statement("GOOGL")
# Returns: "Income Statement for GOOGL: [DataFrame]"
```

### Resources

#### `tickers://search/{stock_name}`

Searches ChromaDB for ticker symbols by company name.

**Example:**

```
Resource URI: tickers://search/Apple
Returns: Query results with ticker metadata
```

## Troubleshooting

### ChromaDB Database Issues

If you encounter ChromaDB errors, delete the `ticker_db/` folder and restart the server to reinitialize.

### MCP Connection Issues

Ensure the server is running before starting the agent. The agent connects via STDIO transport.

### API Rate Limits

Yahoo Finance may rate limit requests. Consider adding delays between multiple stock queries.

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## Support

For issues and questions, please open an issue on the repository.
