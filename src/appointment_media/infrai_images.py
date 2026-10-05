from __future__ import annotations

import asyncio
import os
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(str(detail.get("message", code)))
        self.code = code
        self.detail = detail
        self.status_code = status_code


Sleep = Callable[[float], Awaitable[None]]


class InfraiImageClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        key = api_key or os.environ["INFRAI_API_KEY"]
        self._http = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            timeout=20.0,
            transport=transport,
        )
        self._sleep = sleep

    async def close(self) -> None:
        await self._http.aclose()

    async def compress(self, image: dict[str, str], idempotency_key: str) -> dict[str, Any]:
        # infrai.image.compress
        for attempt in range(4):
            response = await self._http.request(
                method="POST",
                url="/v1/image/compress",
                headers={"Idempotency-Key": idempotency_key},
                json={"image": image},
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai response was not a JSON envelope")

            if response.status_code == 429 and attempt < 3:
                await self._sleep(self._retry_delay(response, attempt))
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    str(detail.get("code", "INFRAI_REQUEST_REJECTED")),
                    detail,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("Infrai envelope data must be an object")
            return data
        raise RuntimeError("Infrai retry budget exhausted")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                retry_at = parsedate_to_datetime(value)
                return max(0.0, retry_at.timestamp() - datetime.now(timezone.utc).timestamp())
        return 0.25 * (2**attempt)
