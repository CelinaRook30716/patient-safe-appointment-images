from typing import Any

import pytest

from appointment_media.service import AppointmentImageRequest, prepare_appointment_image


class RecordingCompressor:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, str], str]] = []

    async def compress(self, image: dict[str, str], idempotency_key: str) -> dict[str, Any]:
        self.calls.append((image, idempotency_key))
        return {"image_id": "img-compressed-42", "format": "webp"}


@pytest.mark.asyncio
async def test_active_appointment_emits_identifier_only_notification() -> None:
    compressor = RecordingCompressor()
    request = AppointmentImageRequest(
        request_id="req-7",
        appointment_id="appt-2048",
        patient_id="patient-31",
        appointment_state="scheduled",
        image={"base64": "c2Nhbi1ieXRlcw=="},
        contains_clinical_detail=False,
    )

    result = await prepare_appointment_image(request, compressor)

    assert compressor.calls == [
        (request.image.model_dump(), "appointment-image:req-7"),
    ]
    assert result.status == "ready"
    assert result.notification.status == "eligible"
    assert result.notification.event == {
        "event": "appointment_image_ready",
        "appointment_id": "appt-2048",
        "patient_id": "patient-31",
        "image_id": "img-compressed-42",
    }
    assert request.image.base64 not in result.model_dump_json()


@pytest.mark.asyncio
async def test_clinical_detail_suppresses_patient_notification() -> None:
    compressor = RecordingCompressor()
    request = AppointmentImageRequest(
        request_id="req-8",
        appointment_id="appt-2048",
        patient_id="patient-31",
        appointment_state="scheduled",
        image={"base64": "c2Nhbi1ieXRlcw=="},
        contains_clinical_detail=True,
    )

    result = await prepare_appointment_image(request, compressor)

    assert result.status == "ready"
    assert result.notification.status == "suppressed"
    assert result.notification.reason == "clinical_detail_present"
    assert result.notification.event is None
