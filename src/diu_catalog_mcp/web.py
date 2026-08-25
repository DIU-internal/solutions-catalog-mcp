from __future__ import annotations

import hmac
import os
from typing import Any

import uvicorn
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .server import _settings, _store, mcp


class ApiKeyMiddleware:
    """Optionally protect only the MCP endpoint with a fixed bearer token."""

    def __init__(self, app: Any, api_key: str) -> None:
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope.get("path", "").startswith("/mcp"):
            headers = {
                key.decode("latin-1").lower(): value.decode("latin-1")
                for key, value in scope.get("headers", [])
            }
            authorization = headers.get("authorization", "")
            bearer = authorization.removeprefix("Bearer ")
            supplied = bearer or headers.get("x-api-key", "")
            if not supplied or not hmac.compare_digest(supplied, self.api_key):
                response = JSONResponse(
                    {"error": "unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


@mcp.custom_route("/", methods=["GET"], include_in_schema=False)
async def service_info(request: Request) -> Response:
    return JSONResponse(
        {
            "name": "DIU Solutions Catalog MCP",
            "status": "ok",
            "mcp_endpoint": "/mcp",
            "health_endpoint": "/health",
            "readiness_endpoint": "/ready",
        }
    )


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health(request: Request) -> Response:
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/ready", methods=["GET"], include_in_schema=False)
async def ready(request: Request) -> Response:
    try:
        count = _store().count()
        if count == 0:
            raise RuntimeError("The vector index is empty")
        return JSONResponse(
            {
                "status": "ready",
                "indexed_records": count,
                "collection": _settings().collection_name,
            }
        )
    except Exception as exc:
        return JSONResponse(
            {"status": "not_ready", "error": str(exc)},
            status_code=503,
        )


def create_app() -> Any:
    middleware: list[Middleware] = []
    api_key = os.getenv("DIU_MCP_API_KEY", "").strip()
    if api_key:
        middleware.append(Middleware(ApiKeyMiddleware, api_key=api_key))
    return mcp.http_app(
        path="/mcp",
        transport="streamable-http",
        stateless_http=True,
        middleware=middleware,
    )


app = create_app()


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port, workers=1, proxy_headers=True)


if __name__ == "__main__":
    main()
