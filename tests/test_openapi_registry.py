from __future__ import annotations

import json
from pathlib import Path

from mirth_connect_mcp.openapi_registry import (
    build_registry_from_spec,
    fallback_action_id,
    load_registry,
    normalize_domain,
)


def test_operation_id_is_preferred_when_present() -> None:
    spec = {
        "paths": {
            "/users": {
                "get": {
                    "tags": ["Users"],
                    "operationId": "getUsers",
                    "parameters": [{"name": "offset", "in": "query", "required": True}],
                }
            }
        }
    }
    registry = build_registry_from_spec(spec)

    users_domain = normalize_domain("Users")
    operation = registry.get_operation(users_domain, "getUsers")

    assert operation is not None
    assert operation.action == "getUsers"
    assert operation.required_query_params == {"offset"}


def test_fallback_action_generation_is_deterministic() -> None:
    spec = {
        "paths": {
            "/channels/{channelId}/messages": {
                "post": {
                    "tags": ["Messages"],
                    "requestBody": {"required": True, "content": {"application/json": {}}},
                }
            }
        }
    }
    registry = build_registry_from_spec(spec)
    messages_domain = normalize_domain("Messages")
    expected_action = fallback_action_id("post", "/channels/{channelId}/messages")

    operation = registry.get_operation(messages_domain, expected_action)
    assert operation is not None
    assert operation.body_required is True


def test_registry_includes_major_known_domains_from_openapi_file() -> None:
    registry = load_registry(Path("openapi_spec/openapi.json"))
    domains = set(registry.domains)

    assert normalize_domain("Channels") in domains
    assert normalize_domain("Connector Services") in domains
    assert normalize_domain("Messages") in domains
    assert normalize_domain("Alerts") in domains
    assert normalize_domain("Users") in domains


def test_openapi_file_has_operations_and_tags() -> None:
    spec = json.loads(Path("openapi_spec/openapi.json").read_text(encoding="utf-8"))
    paths = spec.get("paths") or {}
    operation_count = 0
    for path_item in paths.values():
        for method in path_item.keys():
            if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options", "trace"}:
                operation_count += 1

    assert operation_count > 0
