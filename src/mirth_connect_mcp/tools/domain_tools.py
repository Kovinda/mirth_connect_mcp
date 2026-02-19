from __future__ import annotations

from typing import Any

from ..client import MirthApiClient
from ..models import InvocationEnvelope, error_envelope
from ..openapi_registry import OpenAPIRegistry


async def dispatch_domain_action(
    *,
    domain: str,
    action: str,
    path_params: dict[str, Any] | None,
    query: dict[str, Any] | None,
    body: Any,
    headers_override: dict[str, str] | None,
    registry: OpenAPIRegistry,
    client: MirthApiClient,
    ctx: Any = None,
) -> dict[str, Any]:
    operation = registry.get_operation(domain, action)
    if operation is None:
        return error_envelope(
            status=404,
            domain=domain,
            action=action,
            method="N/A",
            path="N/A",
            error={
                "message": f"Unknown action '{action}' for domain '{domain}'.",
                "suggestion": "Call list_actions(domain) for valid actions.",
            },
        )

    invocation = InvocationEnvelope(
        action=action,
        path_params=path_params or {},
        query=query or {},
        body=body,
        headers_override=headers_override or {},
    )

    missing_path = sorted(
        [param for param in operation.required_path_params if param not in invocation.path_params]
    )
    missing_query = sorted(
        [param for param in operation.required_query_params if param not in invocation.query]
    )

    if missing_path or missing_query or (operation.body_required and invocation.body is None):
        return error_envelope(
            status=400,
            domain=domain,
            action=action,
            method=operation.method,
            path=operation.path,
            error={
                "message": "Validation failed for invocation envelope.",
                "missing_path_params": missing_path,
                "missing_query_params": missing_query,
                "body_required": operation.body_required,
            },
        )

    if operation.request_media_types:
        provided_content_type = invocation.headers_override.get("Content-Type") or invocation.headers_override.get(
            "content-type"
        )
        if provided_content_type and provided_content_type not in operation.request_media_types:
            return error_envelope(
                status=415,
                domain=domain,
                action=action,
                method=operation.method,
                path=operation.path,
                error={
                    "message": "Unsupported Content-Type for this action.",
                    "allowed": operation.request_media_types,
                    "provided": provided_content_type,
                },
            )

    if invocation.body is not None and operation.body_schema_types:
        if "object" in operation.body_schema_types and not isinstance(invocation.body, dict):
            return error_envelope(
                status=400,
                domain=domain,
                action=action,
                method=operation.method,
                path=operation.path,
                error={
                    "message": "Malformed body payload: expected object.",
                    "expected_types": sorted(operation.body_schema_types),
                },
            )

        if isinstance(invocation.body, dict) and operation.body_required_fields:
            missing_body_fields = sorted(
                [field for field in operation.body_required_fields if field not in invocation.body]
            )
            if missing_body_fields:
                return error_envelope(
                    status=400,
                    domain=domain,
                    action=action,
                    method=operation.method,
                    path=operation.path,
                    error={
                        "message": "Malformed body payload: missing required fields.",
                        "missing_body_fields": missing_body_fields,
                    },
                )

    if ctx and hasattr(ctx, "info"):
        maybe_awaitable = ctx.info(
            f"Dispatching {domain}.{action} -> {operation.method} {operation.path}"
        )
        if hasattr(maybe_awaitable, "__await__"):
            await maybe_awaitable

    return await client.execute_operation(domain, operation, invocation)


def register_domain_tools(server: Any, registry: OpenAPIRegistry, client: MirthApiClient) -> None:
    @server.tool(name="list_domains", description="List all available API domains/tags.")
    async def list_domains() -> list[dict[str, str]]:
        return registry.list_domains()

    @server.tool(name="list_actions", description="List available actions for a domain.")
    async def list_actions(domain: str) -> dict[str, Any]:
        actions = registry.list_actions(domain)
        if not actions:
            return {
                "domain": domain,
                "actions": [],
                "error": "Unknown domain. Call list_domains() for valid domains.",
            }
        return {"domain": domain, "actions": actions}

    for domain in sorted(registry.domains.keys()):
        def make_tool(current_domain: str):
            @server.tool(
                name=current_domain,
                description=f"Dispatch NextGen Connect operations for domain '{current_domain}'.",
            )
            async def domain_tool(
                action: str,
                path_params: dict[str, Any] | None = None,
                query: dict[str, Any] | None = None,
                body: Any = None,
                headers_override: dict[str, str] | None = None,
                ctx: Any = None,
            ) -> dict[str, Any]:
                return await dispatch_domain_action(
                    domain=current_domain,
                    action=action,
                    path_params=path_params,
                    query=query,
                    body=body,
                    headers_override=headers_override,
                    registry=registry,
                    client=client,
                    ctx=ctx,
                )

            return domain_tool

        make_tool(domain)
