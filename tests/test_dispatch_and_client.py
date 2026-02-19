from __future__ import annotations

import httpx
import pytest
from pathlib import Path

from mirth_connect_mcp.client import MirthApiClient
from mirth_connect_mcp.config import MirthConfig
from mirth_connect_mcp.models import InvocationEnvelope
from mirth_connect_mcp.openapi_registry import OpenAPIRegistry, OperationMeta
from mirth_connect_mcp.tools.domain_tools import dispatch_domain_action
def _operation() -> OperationMeta:
    return OperationMeta(
        domain="users",
        tag="Users",
        action="getUsers",
        operation_id="getUsers",
        method="GET",
        path="/users/{userId}",
        summary="",
        description="",
        required_path_params={"userId"},
        required_query_params={"limit"},
        body_required=False,
        request_media_types=[],
    )


@pytest.mark.asyncio
async def test_unknown_action_returns_deterministic_error() -> None:
    registry = OpenAPIRegistry(domains={"users": {}}, domain_labels={"users": "Users"})

    class DummyClient:
        async def execute_operation(self, *args, **kwargs):
            raise AssertionError("client should not be called")

    response = await dispatch_domain_action(
        domain="users",
        action="unknown",
        path_params={},
        query={},
        body=None,
        headers_override=None,
        registry=registry,
        client=DummyClient(),
    )

    assert response["status"] == 404
    assert "suggestion" in response["error"]


@pytest.mark.asyncio
async def test_required_param_validation_happens_before_client_call() -> None:
    op = _operation()
    registry = OpenAPIRegistry(domains={"users": {op.action: op}}, domain_labels={"users": "Users"})

    class DummyClient:
        called = False

        async def execute_operation(self, *args, **kwargs):
            self.called = True
            return {}

    dummy = DummyClient()
    response = await dispatch_domain_action(
        domain="users",
        action="getUsers",
        path_params={},
        query={},
        body=None,
        headers_override=None,
        registry=registry,
        client=dummy,
    )

    assert response["status"] == 400
    assert response["error"]["missing_path_params"] == ["userId"]
    assert response["error"]["missing_query_params"] == ["limit"]
    assert dummy.called is False


@pytest.mark.asyncio
async def test_auth_retry_once_on_401_then_success() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/users/_login"):
            return httpx.Response(200, json={"loggedIn": True})
        if len([c for c in calls if c[1].endswith("/users/123")]) == 1:
            return httpx.Response(401, json={"message": "expired"})
        return httpx.Response(200, json={"id": "123"})

    transport = httpx.MockTransport(handler)
    config = MirthConfig(
        base_url="http://example.test/api",
        username="user",
        password="pass",
        verify_ssl=True,
        timeout_seconds=5,
        transport="stdio",
        http_host="127.0.0.1",
        http_port=8000,
        openapi_path=Path("openapi_spec/openapi.json"),
    )
    client = MirthApiClient(config, transport=transport)

    operation = OperationMeta(
        domain="users",
        tag="Users",
        action="getUser",
        operation_id="getUser",
        method="GET",
        path="/users/{userId}",
        summary="",
        description="",
        required_path_params={"userId"},
        required_query_params=set(),
        body_required=False,
        request_media_types=[],
    )

    response = await client.execute_operation(
        "users",
        operation,
        InvocationEnvelope(action="getUser", path_params={"userId": "123"}, query={}),
    )
    await client.close()

    assert response["status"] == 200
    assert response["domain"] == "users"
    assert response["action"] == "getUser"
    assert len([c for c in calls if c[1].endswith("/users/_login")]) == 2
    assert len([c for c in calls if c[1].endswith("/users/123")]) == 2


@pytest.mark.asyncio
async def test_non_2xx_response_is_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/users/_login"):
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(500, json={"message": "boom"})

    transport = httpx.MockTransport(handler)
    config = MirthConfig(
        base_url="http://example.test/api",
        username="user",
        password="pass",
        verify_ssl=True,
        timeout_seconds=5,
        transport="stdio",
        http_host="127.0.0.1",
        http_port=8000,
        openapi_path=Path("openapi_spec/openapi.json"),
    )
    client = MirthApiClient(config, transport=transport)
    op = OperationMeta(
        domain="users",
        tag="Users",
        action="getUsers",
        operation_id="getUsers",
        method="GET",
        path="/users",
        summary="",
        description="",
        required_path_params=set(),
        required_query_params=set(),
        body_required=False,
        request_media_types=[],
    )

    response = await client.execute_operation(
        "users",
        op,
        InvocationEnvelope(action="getUsers"),
    )
    await client.close()

    assert response["status"] == 500
    assert response["method"] == "GET"
    assert response["path"] == "/users"
    assert response["error"]["message"] == "Upstream API error"


@pytest.mark.asyncio
async def test_malformed_body_payload_is_rejected_before_client_call() -> None:
    op = OperationMeta(
        domain="users",
        tag="Users",
        action="createUser",
        operation_id="createUser",
        method="POST",
        path="/users",
        summary="",
        description="",
        required_path_params=set(),
        required_query_params=set(),
        body_required=True,
        request_media_types=["application/json"],
        body_schema_types={"object"},
        body_required_fields={"username"},
    )
    registry = OpenAPIRegistry(domains={"users": {op.action: op}}, domain_labels={"users": "Users"})

    class DummyClient:
        called = False

        async def execute_operation(self, *args, **kwargs):
            self.called = True
            return {}

    dummy = DummyClient()

    response = await dispatch_domain_action(
        domain="users",
        action="createUser",
        path_params={},
        query={},
        body={"not_username": "x"},
        headers_override={"Content-Type": "application/json"},
        registry=registry,
        client=dummy,
    )

    assert response["status"] == 400
    assert "missing_body_fields" in response["error"]
    assert dummy.called is False


@pytest.mark.asyncio
async def test_unsupported_content_type_is_rejected() -> None:
    op = OperationMeta(
        domain="users",
        tag="Users",
        action="createUser",
        operation_id="createUser",
        method="POST",
        path="/users",
        summary="",
        description="",
        required_path_params=set(),
        required_query_params=set(),
        body_required=False,
        request_media_types=["application/json"],
    )
    registry = OpenAPIRegistry(domains={"users": {op.action: op}}, domain_labels={"users": "Users"})

    class DummyClient:
        async def execute_operation(self, *args, **kwargs):
            raise AssertionError("client should not be called")

    response = await dispatch_domain_action(
        domain="users",
        action="createUser",
        path_params={},
        query={},
        body={"username": "x"},
        headers_override={"Content-Type": "text/plain"},
        registry=registry,
        client=DummyClient(),
    )

    assert response["status"] == 415
    assert response["error"]["provided"] == "text/plain"
