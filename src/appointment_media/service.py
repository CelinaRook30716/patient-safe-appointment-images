from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .infrai_images import InfraiError, InfraiImageClient
from .notification_policy import AppointmentState, decide_patient_notification


class ImageReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base64: str = Field(min_length=1)


class AppointmentImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=100)
    appointment_id: str = Field(min_length=1, max_length=100)
    patient_id: str = Field(min_length=1, max_length=100)
    appointment_state: AppointmentState
    image: ImageReference
    contains_clinical_detail: bool
    notification_requested: bool = True


class NotificationResult(BaseModel):
    status: Literal["eligible", "suppressed"]
    reason: str
    event: dict[str, str] | None


class AppointmentImageResult(BaseModel):
    status: Literal["ready"]
    appointment_id: str
    image_id: str
    notification: NotificationResult


async def prepare_appointment_image(
    body: AppointmentImageRequest,
    compressor: Any,
) -> AppointmentImageResult:
    compressed = await compressor.compress(
        body.image.model_dump(),
        idempotency_key=f"appointment-image:{body.request_id}",
    )
    image_id = compressed.get("image_id")
    if not isinstance(image_id, str) or not image_id:
        raise RuntimeError("Compression result did not include image_id")
    decision = decide_patient_notification(
        appointment_id=body.appointment_id,
        patient_id=body.patient_id,
        appointment_state=body.appointment_state,
        contains_clinical_detail=body.contains_clinical_detail,
        notification_requested=body.notification_requested,
        image_id=image_id,
    )
    return AppointmentImageResult(
        status="ready",
        appointment_id=body.appointment_id,
        image_id=image_id,
        notification=NotificationResult(
            status=decision.status,
            reason=decision.reason,
            event=decision.event,
        ),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    client = InfraiImageClient()
    app.state.compressor = client
    yield
    await client.close()


app = FastAPI(title="Appointment Image Gate", lifespan=lifespan)


def get_compressor(request: Request) -> InfraiImageClient:
    return request.app.state.compressor


@app.exception_handler(InfraiError)
async def handle_infrai_error(_request: Request, exc: InfraiError) -> JSONResponse:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(
        status_code=status,
        content={"detail": {"code": exc.code, "message": str(exc)}},
    )


@app.post("/appointment-images", response_model=AppointmentImageResult)
async def compress_appointment_image(
    body: AppointmentImageRequest,
    compressor: InfraiImageClient = Depends(get_compressor),
) -> AppointmentImageResult:
    return await prepare_appointment_image(body, compressor)
