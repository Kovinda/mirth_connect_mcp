from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class InvocationEnvelope:
    action: str
    path_params: dict[str, Any] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    body: Any = None
    headers_override: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ResponseEnvelope:
    status: int
    domain: str
    action: str
    method: str
    path: str
    data: Any = None
    error: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def success_envelope(
    *,
    status: int,
    domain: str,
    action: str,
    method: str,
    path: str,
    data: Any,
) -> dict[str, Any]:
    return ResponseEnvelope(
        status=status,
        domain=domain,
        action=action,
        method=method,
        path=path,
        data=data,
        error=None,
    ).to_dict()


def error_envelope(
    *,
    status: int,
    domain: str,
    action: str,
    method: str,
    path: str,
    error: Any,
) -> dict[str, Any]:
    return ResponseEnvelope(
        status=status,
        domain=domain,
        action=action,
        method=method,
        path=path,
        data=None,
        error=error,
    ).to_dict()
