import httpx
import pytest
import json

from appointment_media.infrai_images import InfraiImageClient


@pytest.mark.asyncio
async def test_rate_limit_honors_retry_after_and_keeps_idempotency_key() -> None:
    requests: list[httpx.Request] = []
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "2"},
                json={"ok": False, "data": None, "error": {"code": "RATE_LIMIT"}, "metadata": {}},
            )
        return httpx.Response(
            200,
            json={"ok": True, "data": {"image_id": "img-9"}, "error": None, "metadata": {}},
        )

    async def record_sleep(seconds: float) -> None:
        delays.append(seconds)

    client = InfraiImageClient(
        "test-key",
        transport=httpx.MockTransport(handler),
        sleep=record_sleep,
    )
    try:
        result = await client.compress({"base64": "YQ=="}, "appointment:req-9")
    finally:
        await client.close()

    assert result == {"image_id": "img-9"}
    assert delays == [2.0]
    assert all(json.loads(request.content) == {"image": {"base64": "YQ=="}} for request in requests)
    assert [request.headers["Idempotency-Key"] for request in requests] == [
        "appointment:req-9",
        "appointment:req-9",
    ]
