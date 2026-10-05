from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AppointmentState = Literal["scheduled", "checked_in", "completed", "cancelled"]


@dataclass(frozen=True)
class NotificationDecision:
    status: Literal["eligible", "suppressed"]
    reason: str
    event: dict[str, str] | None


def decide_patient_notification(
    *,
    appointment_id: str,
    patient_id: str,
    appointment_state: AppointmentState,
    contains_clinical_detail: bool,
    notification_requested: bool,
    image_id: str,
) -> NotificationDecision:
    if not notification_requested:
        return NotificationDecision("suppressed", "not_requested", None)
    if appointment_state not in {"scheduled", "checked_in"}:
        return NotificationDecision("suppressed", "appointment_not_active", None)
    if contains_clinical_detail:
        return NotificationDecision("suppressed", "clinical_detail_present", None)

    return NotificationDecision(
        "eligible",
        "operational_update_only",
        {
            "event": "appointment_image_ready",
            "appointment_id": appointment_id,
            "patient_id": patient_id,
            "image_id": image_id,
        },
    )
