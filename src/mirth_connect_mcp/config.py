from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class MirthConfig:
    base_url: str
    username: str
    password: str
    verify_ssl: bool
    timeout_seconds: float
    transport: str
    http_host: str
    http_port: int
    openapi_path: Path


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigError(
            f"Missing required environment variable: {name}. "
            f"Set {name} before starting the server."
        )
    return value.strip()


def _parse_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean (true/false).")


def load_config() -> MirthConfig:
    base_url = _require_env("MIRTH_BASE_URL")
    username = _require_env("MIRTH_USERNAME")
    password = _require_env("MIRTH_PASSWORD")
    verify_ssl = _parse_bool_env("MIRTH_VERIFY_SSL", True)

    timeout_raw = os.getenv("MIRTH_TIMEOUT_SECONDS", "30").strip()
    try:
        timeout_seconds = float(timeout_raw)
        if timeout_seconds <= 0:
            raise ValueError
    except ValueError as exc:
        raise ConfigError(
            "MIRTH_TIMEOUT_SECONDS must be a positive number."
        ) from exc

    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "streamable-http", "http"}:
        raise ConfigError(
            "MCP_TRANSPORT must be one of: stdio, streamable-http, http"
        )

    http_host = os.getenv("MCP_HTTP_HOST", "127.0.0.1").strip()
    http_port_raw = os.getenv("MCP_HTTP_PORT", "8000").strip()
    try:
        http_port = int(http_port_raw)
    except ValueError as exc:
        raise ConfigError("MCP_HTTP_PORT must be an integer.") from exc

    default_openapi_path = Path(__file__).resolve().parent / "openapi" / "openapi.json"
    openapi_path = Path(os.getenv("MIRTH_OPENAPI_PATH", str(default_openapi_path))).resolve()
    if not openapi_path.exists():
        raise ConfigError(
            f"OpenAPI file not found: {openapi_path}. "
            "Set MIRTH_OPENAPI_PATH to a valid OpenAPI JSON file."
        )

    return MirthConfig(
        base_url=base_url.rstrip("/"),
        username=username,
        password=password,
        verify_ssl=verify_ssl,
        timeout_seconds=timeout_seconds,
        transport="streamable-http" if transport == "http" else transport,
        http_host=http_host,
        http_port=http_port,
        openapi_path=openapi_path,
    )
