# API

All processing endpoints are unauthenticated. Use `X-Timezone` with an IANA timezone such as `America/New_York`; the fallback is `UTC`. AI operations use the configured OpenAI account.

| Endpoint | Request | Response |
|---|---|---|
| `GET /` | None | HTML app shell |
| `GET /favicon.ico` | None | Packaged multi-size icon |
| `GET /api/config` | None | `maxImageSize`, `allowedImageTypes`, `version`, `debug_logging` |
| `POST /process` | Multipart form: optional `text`, repeated `image` files; at least one input | `{ "success": true, "events": [...] }` |
| `POST /correct` | JSON: nonempty `correction`, nonempty array `current_events` | `{ "success": true, "events": [...] }` |
| `POST /download-ics` | JSON: nonempty array `events` | `{ "success": true, "ics_content": "BEGIN:VCALENDAR..." }` |

The browser converts `ics_content` into an `events.ics` download. The endpoint itself returns JSON, not a file attachment.

## Event shape

```json
{
    "title": "Design review",
    "description": "Discuss next month's schedule",
    "start_time": "2026-10-02T10:00:00-04:00",
    "end_time": "2026-10-02T11:00:00-04:00",
    "location_name": "",
    "location_address": ""
}
```

AI responses may also include `location`, `location_details`, and `source_image`. Review model-generated values before exporting. Calendar export requires valid start and end timestamps with end later than start.

## Errors

Errors use `success: false`, `error_type`, and `user_message`:

- HTTP 400: `validation_error` for missing/invalid input, `no_events` for empty results, or `unsafe_prompt` for rejected instructions.
- HTTP 413: `validation_error` when the whole request exceeds 21 MiB.
- HTTP 500: `processing_error` when processing or serialization fails.

The client retains the draft after recoverable failures. Upload MIME validation is not a full image-content security scanner. Unsupported or malformed JSON requests are not a supported API contract.
