from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app import data, main


def test_health_needs_no_key(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_missing_or_wrong_api_key_is_rejected(client):
    assert client.get("/api/v1/screener").status_code == 401
    assert client.get("/api/v1/screener", headers={"X-API-Key": "nope"}).status_code == 401


def test_any_configured_key_is_accepted(client):
    assert client.get("/api/v1/screener", headers={"X-API-Key": "valid-key-2"}).status_code == 200


def test_cors_allows_site_and_localhost_only(client):
    def preflight(origin):
        return client.options(
            "/api/v1/chat",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "x-api-key,content-type"},
        )

    for origin in ("https://sohamchaudhari.in", "http://localhost:3000", "http://127.0.0.1:5173"):
        assert preflight(origin).headers.get("access-control-allow-origin") == origin
    for origin in ("https://evil.com", "https://sohamchaudhari.in.evil.com", "http://localhost.evil.com"):
        assert "access-control-allow-origin" not in preflight(origin).headers


def test_rate_limit_returns_429_with_retry_after(client, auth, monkeypatch):
    monkeypatch.setattr(data, "get_info", lambda ticker: {"symbol": ticker})
    for _ in range(3):
        assert client.get("/api/v1/stocks/AAPL/info", headers=auth).status_code == 200
    resp = client.get("/api/v1/stocks/AAPL/info", headers=auth)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_not_found_and_upstream_errors_map_to_status_codes(client, auth, monkeypatch):
    def missing(ticker, period):
        raise data.NotFoundError("No price data found for 'ZZZZ'.")

    def down(ticker):
        raise data.UpstreamError("Yahoo down")

    monkeypatch.setattr(data, "get_price", missing)
    monkeypatch.setattr(data, "get_info", down)
    assert client.get("/api/v1/stocks/ZZZZ/price", headers=auth).status_code == 404
    assert client.get("/api/v1/stocks/AAPL/info", headers=auth).status_code == 503


def test_invalid_ticker_is_404():
    try:
        data.normalize_ticker("AAPL; DROP")
    except data.NotFoundError:
        return
    raise AssertionError("expected NotFoundError")


def test_chat_returns_reply_thread_and_tools(client, auth, monkeypatch):
    class FakeAgent:
        async def ainvoke(self, payload, config):
            self.thread_id = config["configurable"]["thread_id"]
            return {
                "messages": [
                    HumanMessage("old question"),
                    AIMessage("old answer"),
                    HumanMessage(payload["messages"][0]["content"]),
                    AIMessage("", tool_calls=[{"name": "get_stock_price", "args": {"ticker": "AAPL"}, "id": "1"}]),
                    ToolMessage('{"price": 1}', name="get_stock_price", tool_call_id="1"),
                    AIMessage("AAPL is at $1."),
                ]
            }

    fake = FakeAgent()
    monkeypatch.setattr(main.app.state, "agent", fake)

    resp = client.post("/api/v1/chat", json={"message": "AAPL price?", "thread_id": "my-thread-123"}, headers=auth)
    assert resp.status_code == 200
    assert resp.json() == {"reply": "AAPL is at $1.", "thread_id": "my-thread-123", "tools_used": ["get_stock_price"]}

    resp = client.post("/api/v1/chat", json={"message": "hi"}, headers=auth)
    assert len(resp.json()["thread_id"]) == 32


def test_chat_validates_input(client, auth):
    assert client.post("/api/v1/chat", json={"message": ""}, headers=auth).status_code == 422
    assert client.post("/api/v1/chat", json={"message": "x" * 2001}, headers=auth).status_code == 422
    assert client.post("/api/v1/chat", json={"message": "hi", "thread_id": "../etc"}, headers=auth).status_code == 422
