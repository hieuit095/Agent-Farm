"""HTTP transport that spends a durable scope budget before each request."""

from dataclasses import dataclass

import httpx

from farm_agent.security.state import SecurityGateError


@dataclass(frozen=True)
class HttpObservation:
    status_code: int | None
    body: bytes
    transport_error: str | None = None


class ScopedHttpClient:
    def __init__(self, memory, scan_id: str, *, timeout: float = 5.0):
        self._memory = memory
        self._scan_id = scan_id
        self._client = httpx.AsyncClient(
            timeout=timeout, follow_redirects=False, trust_env=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def request(
        self, method: str, url: str, *, role: str, impact: str,
        headers: dict[str, str] | None = None, content: bytes | None = None,
    ) -> HttpObservation:
        method = method.upper()
        if method not in {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}:
            raise SecurityGateError("Unsupported HTTP method")
        await self._memory.reserve_scoped_request(
            self._scan_id, url=url, role=role, impact=impact, method=method,
        )
        try:
            async with self._client.stream(
                method, url, headers=headers, content=content,
            ) as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 1_048_576:
                        return HttpObservation(None, b"", "response_too_large")
                return HttpObservation(response.status_code, bytes(body))
        except httpx.RequestError as exc:
            return HttpObservation(None, b"", type(exc).__name__)
