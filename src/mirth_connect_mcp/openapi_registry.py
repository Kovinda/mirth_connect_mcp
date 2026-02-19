from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def normalize_domain(tag: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", tag.strip().lower()).strip("_")
    return normalized or "untagged"


def fallback_action_id(method: str, path: str) -> str:
    cleaned = path.strip("/")
    cleaned = re.sub(r"\{([^}]+)\}", r"\1", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", cleaned).strip("_").lower()
    if not cleaned:
        cleaned = "root"
    return f"{method.lower()}_{cleaned}"


@dataclass(slots=True)
class OperationMeta:
    domain: str
    tag: str
    action: str
    operation_id: str
    method: str
    path: str
    summary: str
    description: str
    required_path_params: set[str] = field(default_factory=set)
    required_query_params: set[str] = field(default_factory=set)
    body_required: bool = False
    request_media_types: list[str] = field(default_factory=list)
    body_schema_types: set[str] = field(default_factory=set)
    body_required_fields: set[str] = field(default_factory=set)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "operation_id": self.operation_id,
            "method": self.method,
            "path": self.path,
            "summary": self.summary,
            "required_path_params": sorted(self.required_path_params),
            "required_query_params": sorted(self.required_query_params),
            "body_required": self.body_required,
            "request_media_types": self.request_media_types,
            "body_schema_types": sorted(self.body_schema_types),
            "body_required_fields": sorted(self.body_required_fields),
        }


@dataclass(slots=True)
class OpenAPIRegistry:
    domains: dict[str, dict[str, OperationMeta]]
    domain_labels: dict[str, str]

    def list_domains(self) -> list[dict[str, str]]:
        return [
            {"domain": domain, "label": self.domain_labels[domain]}
            for domain in sorted(self.domains)
        ]

    def list_actions(self, domain: str) -> list[dict[str, Any]]:
        actions = self.domains.get(domain)
        if not actions:
            return []
        return [actions[action].to_public_dict() for action in sorted(actions)]

    def get_operation(self, domain: str, action: str) -> OperationMeta | None:
        return self.domains.get(domain, {}).get(action)


def _collect_parameters(path_item: Mapping[str, Any], operation: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    return _collect_parameters_with_resolver(path_item, operation, None)


class _SpecResolver:
    def __init__(self, spec: Mapping[str, Any]) -> None:
        self._spec = spec

    def resolve_ref(self, maybe_ref: Any) -> Any:
        if not isinstance(maybe_ref, Mapping):
            return maybe_ref
        ref = maybe_ref.get("$ref")
        if not isinstance(ref, str):
            return maybe_ref
        if not ref.startswith("#/"):
            return maybe_ref
        node: Any = self._spec
        for part in ref[2:].split("/"):
            if isinstance(node, Mapping) and part in node:
                node = node[part]
            else:
                return maybe_ref
        return node

    def resolve_schema(self, schema: Any, depth: int = 0) -> Any:
        if depth > 8:
            return schema
        resolved = self.resolve_ref(schema)
        if resolved is schema:
            return schema
        return self.resolve_schema(resolved, depth + 1)


def _collect_parameters_with_resolver(
    path_item: Mapping[str, Any],
    operation: Mapping[str, Any],
    resolver: _SpecResolver | None,
) -> tuple[set[str], set[str]]:
    required_path: set[str] = set()
    required_query: set[str] = set()
    combined = [*(path_item.get("parameters") or []), *(operation.get("parameters") or [])]
    for parameter in combined:
        if resolver is not None:
            parameter = resolver.resolve_ref(parameter)
        if not isinstance(parameter, Mapping):
            continue
        if not parameter.get("required"):
            continue
        name = str(parameter.get("name", "")).strip()
        location = str(parameter.get("in", "")).strip()
        if not name:
            continue
        if location == "path":
            required_path.add(name)
        elif location == "query":
            required_query.add(name)
    return required_path, required_query


def _extract_body_schema_hints(
    request_body: Mapping[str, Any], resolver: _SpecResolver | None
) -> tuple[set[str], set[str]]:
    body_schema_types: set[str] = set()
    body_required_fields: set[str] = set()
    content = request_body.get("content") or {}
    for media_payload in content.values():
        if not isinstance(media_payload, Mapping):
            continue
        schema = media_payload.get("schema")
        if resolver is not None:
            schema = resolver.resolve_schema(schema)
        if not isinstance(schema, Mapping):
            continue

        schema_type = schema.get("type")
        if isinstance(schema_type, str):
            body_schema_types.add(schema_type)

        if "oneOf" in schema and isinstance(schema.get("oneOf"), list):
            for option in schema.get("oneOf"):
                opt_schema = resolver.resolve_schema(option) if resolver else option
                if isinstance(opt_schema, Mapping):
                    option_type = opt_schema.get("type")
                    if isinstance(option_type, str):
                        body_schema_types.add(option_type)

        if "anyOf" in schema and isinstance(schema.get("anyOf"), list):
            for option in schema.get("anyOf"):
                opt_schema = resolver.resolve_schema(option) if resolver else option
                if isinstance(opt_schema, Mapping):
                    option_type = opt_schema.get("type")
                    if isinstance(option_type, str):
                        body_schema_types.add(option_type)

        if schema.get("type") == "object" and isinstance(schema.get("required"), list):
            body_required_fields.update(
                [str(field) for field in schema.get("required") if isinstance(field, str)]
            )
    return body_schema_types, body_required_fields


def build_registry_from_spec(spec: Mapping[str, Any]) -> OpenAPIRegistry:
    domains: dict[str, dict[str, OperationMeta]] = {}
    domain_labels: dict[str, str] = {}
    paths = spec.get("paths") or {}
    resolver = _SpecResolver(spec)

    for path, path_item in paths.items():
        if not isinstance(path_item, Mapping):
            continue
        for method, operation in path_item.items():
            method_l = method.lower()
            if method_l not in HTTP_METHODS or not isinstance(operation, Mapping):
                continue

            tags = operation.get("tags") or ["untagged"]
            tag = str(tags[0])
            domain = normalize_domain(tag)

            action = str(operation.get("operationId") or "").strip()
            if not action:
                action = fallback_action_id(method_l, path)

            required_path, required_query = _collect_parameters_with_resolver(
                path_item, operation, resolver
            )

            request_body = operation.get("requestBody") or {}
            request_body = resolver.resolve_ref(request_body)
            if not isinstance(request_body, Mapping):
                request_body = {}
            body_required = bool(request_body.get("required"))
            content = request_body.get("content") or {}
            media_types = sorted([str(media_type) for media_type in content.keys()])
            body_schema_types, body_required_fields = _extract_body_schema_hints(
                request_body, resolver
            )

            meta = OperationMeta(
                domain=domain,
                tag=tag,
                action=action,
                operation_id=action,
                method=method_l.upper(),
                path=str(path),
                summary=str(operation.get("summary") or ""),
                description=str(operation.get("description") or ""),
                required_path_params=required_path,
                required_query_params=required_query,
                body_required=body_required,
                request_media_types=media_types,
                body_schema_types=body_schema_types,
                body_required_fields=body_required_fields,
            )

            domain_bucket = domains.setdefault(domain, {})
            domain_bucket[action] = meta
            domain_labels.setdefault(domain, tag)

    return OpenAPIRegistry(domains=domains, domain_labels=domain_labels)


def load_registry(openapi_path: str | Path) -> OpenAPIRegistry:
    path = Path(openapi_path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    return build_registry_from_spec(spec)
