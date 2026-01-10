import asyncio
import os
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()


async def main(input: str):
    # 1️⃣ Groq LLM (replaces LiteLLM + Ollama)
    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="openai/gpt-oss-120b",  # or llama3-70b-8192
        temperature=0,
    )

    # 2️⃣ MCP Server via STDIO (same as smolagents)
    mcp_client = MultiServerMCPClient(
        {
            "financial_mcp": {
                "transport": "stdio",
                "command": "uv",
                "args": ["run", "server.py"],
                "env": None,
            }
        }
    )

    # 3️⃣ Load MCP tools
    tools = await mcp_client.get_tools()
    
    # 4️⃣ Create ReAct agent with tools
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt="""
        You are a financial analysis agent. Use the provided tools to answer user queries about stock prices and company information.
        Be sure to cite your sources using the tool calls.""",

    )
    
    # 5️⃣ Run query
    response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": input}]}
    )

    print("\nAgent:", response["messages"][-1].content)


if __name__ == "__main__":
    input = input("Enter a query: ")
    asyncio.run(main(input))
# To run: python agent.py