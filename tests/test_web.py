from __future__ import annotations

from starlette.testclient import TestClient

from diu_catalog_mcp import web


class ReadyStore:
    def count(self) -> int:
        return 137


def test_health_and_readiness_routes(monkeypatch) -> None:
    monkeypatch.delenv("DIU_MCP_API_KEY", raising=False)
    monkeypatch.setattr(web, "_store", lambda: ReadyStore())
    with TestClient(web.create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json()["indexed_records"] == 137
        assert client.get("/").json()["mcp_endpoint"] == "/mcp"


def test_optional_api_key_protects_only_mcp(monkeypatch) -> None:
    monkeypatch.setenv("DIU_MCP_API_KEY", "test-secret")
    with TestClient(web.create_app()) as client:
        unauthorized = client.get("/mcp")
        assert unauthorized.status_code == 401
        assert unauthorized.headers["www-authenticate"] == "Bearer"
        assert client.get("/health").status_code == 200

        authorized = client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer test-secret",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            content="{}",
        )
        assert authorized.status_code != 401
