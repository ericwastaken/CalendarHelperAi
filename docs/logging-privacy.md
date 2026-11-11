# Logging privacy contract

Personal data must never be written to CalendarHelperAI's application operational
logs. Submitted images, text and calendar content are excluded at the source;
this pipeline is for diagnosing requests, not recording their contents.

This contract applies to the supplied application and supervised container.
It is enforced by code and regression tests, not by a promise that redaction
will recognize every sensitive string. Never add free-text payload fields.

## Never recorded

- Images, base64, upload filenames and multipart bodies.
- Submitted text, corrections, model prompts or responses, event titles,
    appointment dates/times, names, addresses, descriptions and generated ICS.
- Client IPs, request URLs/query strings, user agents, cookies and headers.
- API keys, credentials, raw exception messages or stack traces.
- Provider request IDs or arbitrary provider error strings.

Operational timestamps record when a request ran, not when an appointment occurs.
Random request/event IDs support troubleshooting without identifying a user.
Keep archives private anyway: timings and counts still describe service activity.
Do not put personal names, emails or secrets in deployment labels, bucket names
or object prefixes. The collector copies these operator-controlled identifiers.

## What is recorded

Every structured event includes `timestamp` (UTC), `event_id` (random UUID hex),
`request_id` (generated per HTTP request, null for startup), `schema_version` (1),
installed application `version`, `level`, and an approved `event` name.

| Event | Purpose |
|---|---|
| `application_started` | Application factory initialized |
| `processing_started` | Extraction began; image count |
| `provider_usage` | API response received; configured model category and available numeric token counts, before calendar validation |
| `provider_completed` | Model call completed; outcome, event count, elapsed time, model |
| `provider_failed` | Categorized provider failure, timing and optional HTTP status/code |
| `request_rejected` | Model classified a non-calendar request |
| `processing_failed` | Typed error returned to the caller |
| `validation_failed` | Request validation failed |
| `unexpected_failure` | Internal failure, without exception text |
| `request_finished` | HTTP status, route stage, duration and success/failure |

Optional fields are `stage`, `outcome`, `elapsed_ms`, `image_count`, `event_count`,
`status`, `error_type`, `exception_class`, `provider_status`, `provider_code`, and
`model`, `input_tokens`, `output_tokens`, and `cached_input_tokens`. String values are finite approved categories; numeric values are bounded.
Unknown fields and invalid values are dropped. The exact approved categories and
bounds live in [observability.py](../src/calendar_helper_ai/observability.py).
A new category requires a code change and privacy review.

Only `/process`, `/correct`, `/resolve-time` and `/download-ics` emit request
summaries. Health, page and static-asset requests are quiet. Fluent Bit adds
`project`, `environment`, `service`, `instance` and may add its own `date` timestamp.
No client identity is added. Join related events by `request_id`, and deduplicate
retries by `event_id`; several events per request are expected.

## Token usage accounting

Version 1.3.0 adds one `provider_usage` event per returned Chat Completions response,
for extraction and correction. It reads only `usage.prompt_tokens`,
`usage.completion_tokens` and `usage.prompt_tokens_details.cached_tokens`, mapping
them to `input_tokens`, `output_tokens` and `cached_input_tokens`. Counts must be
actual integers from 0 through 1,000,000,000; booleans, strings, fractions, negatives
and larger values are discarded. Missing usage remains absent, not a fabricated
zero. Cached input is included in input tokens and is omitted if input is missing
or the cached count exceeds it. Never add cached input to the input total.

Usage is emitted before interpreting the calendar answer, so an unsupported or
malformed answer can still have usage. Exceptions without a response have no
fabricated usage event. The SDK may retry, and interruptions or buffer loss may
hide consumption; these records are diagnostic rather than a billing ledger.
Only `provider_usage` carries token counts, avoiding double counting successful
requests through `provider_completed`. Deduplicate by event ID before summing.
OpenAI usage/cost reports remain authoritative for billing. No dollar estimate
is logged, and a usage event with missing counts does not prove zero cost.

Model labels describe the configured ID, not the provider's returned snapshot.
Approved labels are `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`,
`gpt-4.1-nano` and `other`. This is a privacy vocabulary, not a claim that those
models are currently available or tested. Unlisted operator-supplied IDs map to
`other`; arbitrary configuration/provider strings never enter logs. New optional
fields preserve schema version 1; readers of older logs should use nullable
integer columns. `LOGGING_ENABLED=false` suppresses usage events as well.

## Enforcement

The emitter validates both names and values. Output handlers reject ordinary
Flask logger messages, including free-text errors and tracebacks, instead of
assuming every caller used the emitter. Payload-capable SDK/HTTP/server loggers
are suppressed before the AI client is created. Legacy OpenAI log-level variables
cannot re-enable verbose payload logging. `DEBUG_LOGGING` does not bypass this.
The unused IP-location helper does not log raw exception text.

The supplied container and legacy Procfile direct Gunicorn access/error logs to
`/dev/null`. This deliberately gives up raw server tracebacks and malformed-request
diagnostics that could contain IPs or request fragments. Use categorized events,
health status and exit status for operational investigation. Fluent Bit and the
supervisor can emit infrastructure diagnostics separately from the JSON archive;
they never ingest HTTP payloads. Do not enable trace-level collector diagnostics,
custom access logs, debuggers or third-party tracing without another privacy review.

`LOGGING_ENABLED=false` disables all application operational output and the
container collector. See [disable instructions](container-logging.md#disable-logging-completely).

## Boundary of the claim

This is an application logging contract, not a blanket claim that personal data
is never processed, temporarily stored, or retained by any service. Submitted
content is sent to OpenAI for processing. Multipart handling may spool uploads
to temporary disk; the browser holds drafts in memory and saves downloads on
request. Provider/CDN/load-balancer access logs, AI provider retention, Docker
host auditing and arbitrary operator-installed instrumentation have independent
policies. The application toggle cannot disable them. Review those controls
separately when deploying a fork.

Privacy hardening in v1.2.1 does not rewrite or erase older archives. Older
versions allowed verbose SDK logs and free-text Flask messages; do not apply the
new enforcement guarantee retroactively. Optional legacy fields can remain in
query schemas when reading older logs, but v1.2.1 no longer emits provider IDs.

## Regression checks

The offline suite tests real SDK calls with an in-memory HTTP transport, including
verbose legacy settings, hostile provider error values and synthetic sensitive
markers. It also tests direct logger bypass attempts, output filtering, disabled
logging, request correlation and container lifecycle. No personal fixtures or
real API calls are needed. Run the complete suite and review this document when
changing routes, AI SDKs, logging configuration or process startup.
