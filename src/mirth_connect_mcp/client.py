from __future__ import annotations

from typing import Any

import httpx

from .config import MirthConfig
from .models import InvocationEnvelope, error_envelope, success_envelope
from .openapi_registry import OperationMeta


class MirthApiClient:
    def __init__(self, config: MirthConfig, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._config = config
        self._transport = transport
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=self._config.timeout_seconds,
            transport=self._transport,
            verify=self._config.verify_ssl,
            headers={"X-Requested-With": "OpenAPI"},
        )
        self._authenticated = False

    async def close(self) -> None:
        await self._client.aclose()

    async def _login(self) -> None:
        response = await self._client.post(
            "/users/_login",
            data={
                "username": self._config.username,
                "password": self._config.password,
            },
        )
        if response.status_code >= 400:
            self._authenticated = False
            raise PermissionError(f"Login failed with status {response.status_code}")
        self._authenticated = True

    async def _request(self, operation: OperationMeta, invocation: InvocationEnvelope) -> httpx.Response:
        try:
            path = operation.path.format(**invocation.path_params)
        except KeyError as exc:
            missing = str(exc).strip("\"'")
            raise KeyError(f"Missing path param: {missing}") from exc

        headers: dict[str, str] = {}
        headers.update(invocation.headers_override)
        response = await self._client.request(
            operation.method,
            path,
            params=invocation.query,
            json=invocation.body,
            headers=headers,
        )
        return response

    @staticmethod
    def _decode_response_content(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    async def execute_operation(
        self,
        domain: str,
        operation: OperationMeta,
        invocation: InvocationEnvelope,
    ) -> dict[str, Any]:
        if not self._authenticated:
            try:
                await self._login()
            except PermissionError as exc:
                return error_envelope(
                    status=401,
                    domain=domain,
                    action=operation.action,
                    method=operation.method,
                    path=operation.path,
                    error={"message": str(exc), "type": "auth_error"},
                )

        retried = False
        while True:
            try:
                response = await self._request(operation, invocation)
            except KeyError as exc:
                return error_envelope(
                    status=400,
                    domain=domain,
                    action=operation.action,
                    method=operation.method,
                    path=operation.path,
                    error={"message": str(exc), "type": "validation_error"},
                )
            except httpx.TimeoutException as exc:
                return error_envelope(
                    status=0,
                    domain=domain,
                    action=operation.action,
                    method=operation.method,
                    path=operation.path,
                    error={"message": str(exc), "type": "timeout"},
                )
            except httpx.HTTPError as exc:
                return error_envelope(
                    status=0,
                    domain=domain,
                    action=operation.action,
                    method=operation.method,
                    path=operation.path,
                    error={"message": str(exc), "type": "transport_error"},
                )

            if response.status_code in {401, 403} and not retried:
                retried = True
                self._authenticated = False
                try:
                    await self._login()
                except PermissionError as exc:
                    return error_envelope(
                        status=response.status_code,
                        domain=domain,
                        action=operation.action,
                        method=operation.method,
                        path=operation.path,
                        error={"message": str(exc), "type": "auth_error"},
                    )
                continue

            payload = self._decode_response_content(response)
            if 200 <= response.status_code < 300:
                return success_envelope(
                    status=response.status_code,
                    domain=domain,
                    action=operation.action,
                    method=operation.method,
                    path=operation.path,
                    data=payload,
                )

            return error_envelope(
                status=response.status_code,
                domain=domain,
                action=operation.action,
                method=operation.method,
                path=operation.path,
                error={"message": "Upstream API error", "payload": payload},
            )
