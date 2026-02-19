from __future__ import annotations

import asyncio
from typing import Any

from .client import MirthApiClient
from .config import MirthConfig, load_config
from .openapi_registry import OpenAPIRegistry, load_registry
from .tools.domain_tools import register_domain_tools


def _load_fastmcp() -> Any:
    try:
        from fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "fastmcp is not installed. Install dependencies first (for example: uv sync --dev)."
        ) from exc
    return FastMCP


def create_server(
    config: MirthConfig | None = None,
    registry: OpenAPIRegistry | None = None,
    client: MirthApiClient | None = None,
) -> tuple[Any, MirthConfig, OpenAPIRegistry, MirthApiClient]:
    runtime_config = config or load_config()
    runtime_registry = registry or load_registry(runtime_config.openapi_path)
    runtime_client = client or MirthApiClient(runtime_config)

    FastMCP = _load_fastmcp()
    server = FastMCP(name="mirth-nextgen-connect")
    register_domain_tools(server, runtime_registry, runtime_client)
    return server, runtime_config, runtime_registry, runtime_client


def run() -> None:
    server, config, _, _ = create_server()

    if config.transport == "stdio":
        if hasattr(server, "run_stdio"):
            server.run_stdio()
            return
        server.run()
        return

    if hasattr(server, "run_streamable_http"):
        server.run_streamable_http(host=config.http_host, port=config.http_port)
        return

    if hasattr(server, "run_streamable_http_async"):
        asyncio.run(server.run_streamable_http_async(host=config.http_host, port=config.http_port))
        return

    raise RuntimeError("FastMCP runtime does not provide Streamable HTTP run methods.")
