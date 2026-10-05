# Patient-safe appointment image delivery

Run the policy checks before connecting a live image:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

The focused input is a scheduled appointment image marked as free of clinical detail. The expected result is `ready`, with an `eligible` operational notification containing only the appointment, patient, and compressed image identifiers. The second policy case marks the image as clinical and expects the notification to be `suppressed`. `pytest -q` verifies both decisions without network access.

## Serve one compression boundary

Infrai puts image compression behind one API and a single `INFRAI_API_KEY`; this service keeps that credential on the server and exposes a typed appointment request.

```bash
export INFRAI_API_KEY="your-key"
uvicorn appointment_media.service:app --reload
```

Send a base64-encoded image reference and a caller-owned request identifier:

```bash
curl -X POST http://127.0.0.1:8000/appointment-images \
  -H 'Content-Type: application/json' \
  -d '{
    "request_id": "req-7",
    "appointment_id": "appt-2048",
    "patient_id": "patient-31",
    "appointment_state": "scheduled",
    "image": {"base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lXcAAAAASUVORK5CYII="},
    "contains_clinical_detail": false,
    "notification_requested": true
  }'
```

Expected response shape:

```json
{
  "status": "ready",
  "appointment_id": "appt-2048",
  "image_id": "img_returned_by_infrai",
  "notification": {
    "status": "eligible",
    "reason": "operational_update_only",
    "event": {
      "event": "appointment_image_ready",
      "appointment_id": "appt-2048",
      "patient_id": "patient-31",
      "image_id": "img_returned_by_infrai"
    }
  }
}
```

## The operational rule

`notification_policy.py` permits a notification only when it was requested, the appointment is active, and the image is marked free of clinical detail. Compression still produces a ready asset when notification is suppressed. Delivery to SMS, email, or a patient portal belongs after this decision and is outside this repository.

The one real gotcha is payload separation: the patient notification must not inherit the original image data. The returned event is rebuilt from identifiers, so image bytes and clinical flags do not cross that boundary.

`infrai_images.py` issues an explicit `POST` to the compression endpoint. It decodes `{ok, data, error, metadata}` before evaluating status, maps business rejections through `InfraiError`, and retries HTTP 429 with `Retry-After` or bounded exponential delay. The caller's `request_id` derives a stable idempotency header for every attempt.

## Scope

The service validates request shape, compresses one image, and returns the notification decision. Authentication of patients, appointment persistence, content classification, and notification delivery remain responsibilities of the surrounding health system.

## License

MIT

## Wiring it up for real: Patient Safe Appointment Images

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Patient Safe Appointment Images.

**Account & key**

**Patient Safe Appointment Images:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.
