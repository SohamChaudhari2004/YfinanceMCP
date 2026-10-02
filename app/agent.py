"""The stock-analysis agent: Groq LLM + stock tools + per-thread conversation memory."""

import asyncio
from datetime import datetime, timezone
from weakref import WeakValueDictionary

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ModelRequest, before_model, dynamic_prompt
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from app.config import settings
from app.tools import ALL_TOOLS

SYSTEM_PROMPT = """You are a financial research assistant for stocks, ETFs and funds.

- Always use the tools for prices, company data, financials and screens. Never invent numbers.
- If the user gives a company name, call search_ticker first to find the right symbol.
- If a tool returns ERROR, say so plainly instead of guessing.
- Mention the data source (Yahoo Finance) and the as-of date for prices; data may be delayed.
- Answer concisely in Markdown. Use tables for comparisons.
- You give information, not personalised investment advice."""


@dynamic_prompt
def system_prompt_with_date(request: ModelRequest) -> str:
    # Without today's date the model guesses a year from its training data.
    today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    return f"{SYSTEM_PROMPT}\n\nToday's date (UTC) is {today}."


@before_model
def trim_history(state, runtime):
    """Drop the oldest turns so a thread never exceeds MAX_HISTORY_MESSAGES.

    Cuts only at user-message boundaries so tool calls and their results stay paired.
    """
    messages = state["messages"]
    limit = settings.max_history_messages
    if len(messages) <= limit:
        return None
    human_indexes = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    start = next((i for i in human_indexes if len(messages) - i <= limit), human_indexes[-1] if human_indexes else 0)
    if start == 0:
        return None
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *messages[start:]]}


def build_agent(checkpointer):
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0,
        max_retries=2,
        timeout=60,
    )
    return create_agent(
        model=llm,
        tools=ALL_TOOLS,
        checkpointer=checkpointer,
        middleware=[system_prompt_with_date, trim_history, ModelCallLimitMiddleware(run_limit=8, exit_behavior="end")],
    )


# One in-flight request per thread, so concurrent calls can't interleave a conversation.
_thread_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


def _lock_for(thread_id: str) -> asyncio.Lock:
    lock = _thread_locks.get(thread_id)
    if lock is None:
        lock = asyncio.Lock()
        _thread_locks[thread_id] = lock
    return lock


async def ask(agent, message: str, thread_id: str) -> tuple[str, list[str]]:
    """Run one user turn. Returns (reply, names of tools called during this turn)."""
    lock = _lock_for(thread_id)
    async with lock:
        result = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [{"role": "user", "content": message}]},
                config={"configurable": {"thread_id": thread_id}},
            ),
            timeout=settings.agent_timeout_seconds,
        )

    messages = result["messages"]
    last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    turn = messages[last_human + 1:]
    tools_used = list(dict.fromkeys(m.name for m in turn if isinstance(m, ToolMessage)))
    reply = next((m.text for m in reversed(turn) if isinstance(m, AIMessage) and m.text), "")
    return reply or "Sorry, I couldn't produce an answer for that. Please rephrase.", tools_used
