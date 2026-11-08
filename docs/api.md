# API

All processing endpoints are unauthenticated. Use `X-Timezone` with an IANA timezone such as `America/New_York`; the fallback is `UTC`. AI operations use the configured OpenAI account.

| Endpoint | Request | Response |
|---|---|---|
| `GET /` | None | HTML app shell |
| `GET /favicon.ico` | None | Packaged multi-size icon |
| `GET /api/config` | None | `maxImageSize`, `allowedImageTypes`, `version`, `debug_logging` |
| `POST /process` | Multipart form: optional `text`, repeated `image` files; at least one input | `{ "success": true, "events": [...] }` |
| `POST /correct` | JSON: nonempty `correction`, nonempty array `current_events` | `{ "success": true, "events": [...] }` |
| `POST /resolve-time` | JSON: `event`, `mode` (`timed`, `all_day`, `confirm_duration`); timed mode also requires `start_local` and `end_local`; all-day accepts `date` | `{ "success": true, "event": {...} }` |
| `POST /download-ics` | JSON: nonempty array `events` | `{ "success": true, "ics_content": "BEGIN:VCALENDAR..." }` |

The browser converts `ics_content` into an `events.ics` download. The endpoint itself returns JSON, not a file attachment.

## Event shape

```json
{
    "title": "Design review",
    "description": "Discuss next month's schedule",
    "date": "2026-10-02",
    "time_status": "timed",
    "start_time": "2026-10-02T10:00:00-04:00",
    "end_time": "2026-10-02T11:00:00-04:00",
    "location_name": "",
    "location_address": ""
}
```

`time_status` is `timed`, `missing`, or `all_day`. Missing times have null `start_time` and `end_time`, with a date when known. All-day events use `date` and exclusive `end_date`; `all_day_source: user` identifies an explicit reminder choice. Timed events without an end get `duration_assumed: true` and `duration_confirmed: false` until the user confirms or edits the duration. Export rejects unresolved times and unconfirmed durations. Legacy timed drafts without `time_status` remain accepted at the export boundary.

The time-resolution endpoint takes local ISO date/time values without offsets, interpreted in `X-Timezone`. Explicitly selected start and end times must form a positive interval. Unknown dates require user input before export. A date-only all-day export never shifts with the user's timezone.

## Errors and diagnostics

Processing JSON responses include a generated `request_id`, also returned in `X-Request-ID`. Errors contain `success: false`, `error_type`, and a fixed/actionable `user_message`. The UI appends the reference ID so operators can correlate a report without asking for private appointment details.

- HTTP 400: invalid input, unresolved time/duration, `no_events`, or `unsupported_request`.
- HTTP 413: upload envelope exceeds 21 MiB.
- HTTP 429: provider rate limiting.
- HTTP 502: provider failure or invalid model response.
- HTTP 503: provider authentication/configuration, exhausted quota, or connection failure.
- HTTP 504: provider timeout.
- HTTP 500: unexpected internal failure.

Provider credentials failing do not imply the user's request is unsafe. Logs use safe error categories, exception classes, status/code and provider request identifiers without response bodies. All recoverable browser failures retain the draft. Upload MIME validation is not a full image-content security scanner.
