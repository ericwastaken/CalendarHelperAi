# Architecture and repository layout

Calendar Helper AI is one Flask application serving a vanilla JavaScript frontend and JSON endpoints. OpenAI handles combined image-aware suitability/extraction and contextual corrections. The `icalendar` library produces calendar files. The active workflow has no application database or user-account system.

## Layout

```text
src/calendar_helper_ai/
    __init__.py                 Application factory
    config.py                   Runtime configuration and upload limits
    routes.py                   Blueprint with page and API routes
    observability.py            Allowlisted JSON operational logs and request IDs
    prompts.py                  AI prompt templates
    services/
        ai_processor.py         Multimodal extraction, corrections, typed provider errors
        events.py               Time states, normalization and explicit time resolution
        calendar.py             ICS generation and timezone handling
        location.py             Legacy IP lookup helper, not called by current routes
    templates/index.html        Application shell
    static/                     CSS, JavaScript, icons, images, terms, example walkthrough
tests/                          Offline regression and package contracts
docs/                           Detailed documentation and design history
pyproject.toml                  Package metadata, dependencies, build configuration
uv.lock                         Locked dependency resolution
.python-version                 Python runtime selection
Dockerfile                      Application image with Gunicorn and Fluent Bit
compose.yaml                    Local development mounts and ports
compose.logging-disabled.yaml   Standalone local container without log collection
container/                      Process supervision, collector config and health probe
Procfile                        Legacy buildpack Gunicorn entry point
.do/app.yaml                    Generic creation template
```

The `src` layout separates importable code from repository tools and documentation. Install the package with `uv sync --locked`; do not rely on setting `PYTHONPATH`. Static files and templates are package data included in the wheel. Browser URLs remain `/static/...` even though the files live beneath `src`.

The container owns its Fluent Bit collector. The supervised runtime routes the
same operational event stream to local files in dev or a configured remote bucket
in production. A separate local DuckDB workspace reads those files; it is not an
application dependency. See [container logging](container-logging.md) for the
schema, process lifecycle, buffering and durability limits.

## Application creation

`create_app()` loads `.env` from the current working directory without replacing existing environment values, reads configuration, creates an application-owned OpenAI client when a key is supplied, and registers the route blueprint. Importing modules does not create a global Flask app or AI client. Tests pass configuration and a fake `OPENAI_CLIENT` directly and skip dotenv loading.

Each application owns its configuration and client. Flask CLI discovers `create_app`; Gunicorn uses `calendar_helper_ai:create_app()`. Application version comes from installed package metadata, maintained in `pyproject.toml`.

## Request flow

1. The browser gets upload limits and version from `/api/config`.
2. `/process` validates multipart uploads and text. It rejects more than five images, unsupported MIME types, files above 4 MiB, and requests above the 21 MiB envelope.
3. One request using `OPENAI_MODEL` (default `gpt-4o`) sees the text and all images together. It returns events, no events, or an unsupported-task result. There is no text-only preflight that can reject terse instructions before seeing images. Corrections use the same configured model and receive all existing events and their time states. A numeric `provider_usage` event records returned token counts before calendar-response validation, including responses later rejected as malformed or unsupported.
4. Event normalization distinguishes `timed`, `missing`, and `all_day`. Unknown times stay null. A known start without an end gets a suggested one-hour duration that requires confirmation. Supplied address text is preserved without a second model lookup that might invent an address.
5. `/resolve-time` records an explicit time, an all-day reminder choice, or confirmation of a suggested duration. Local times are validated in the user's IANA timezone; nonexistent and ambiguous daylight-saving times require a different selection.
6. `/download-ics` rejects unresolved times and unconfirmed durations. Timed events preserve their instants; all-day events use date-only values and an exclusive end date. Events involving the repeated daylight-saving hour use UTC to retain the intended instant.

The existing IP location helper is retained for reference but is not connected to the active routes. Missing month/day values are not fabricated. Missing years may use the current local year, as described in the extraction prompt.

## Frontend phases

The frontend moves through input, processing, review/correction, and export confirmation. Recoverable errors preserve inputs or reviewed events. Export downloads a file; it does not add events to a calendar automatically. Reset is confirmed before clearing reviewed work. Example, image-preview, terms, and reset dialogs use native browser dialogs.

Drafts, images, correction history, and results live in JavaScript memory. Refresh or closing the page clears that state. The session expires after one hour without an extension, with a warning during the last five minutes; pending operations defer expiration. The dated [design implementation](design-system/paper-pine-2026-09/IMPLEMENTATION.md) describes components and recovery behavior.

## Data handling

The application sends submitted text and images to OpenAI. It does not write appointment records to an application database. Browser downloads are saved by the user, and service providers may retain requests or logs according to their own policies. Server upload handling may spool larger multipart files to temporary storage. This is not a guarantee of memory-only processing or regulatory compliance.

Operational logs contain only validated operational metadata, never submitted
personal content. The app filters ordinary free-text log messages and suppresses
payload-capable dependency diagnostics. The supplied container disables Gunicorn
access/error logs, which could otherwise contain client IPs or request fragments.
Read [logging privacy](logging-privacy.md) for the exact contract, schema and
boundaries. `LOGGING_ENABLED=false` disables the operational stream and container
collector completely; readiness and request IDs continue to work. Successful
readiness probes do not produce application request logs. Configure retention for
local output and remote objects separately. Hosting-provider access logs and AI
provider retention are outside this application's controls.

The current app does not use Flask sessions or set cookies, and the frontend does
not use localStorage, sessionStorage or tracking scripts. A configured Flask
signing key does not itself create a cookie. Hosting/CDN security cookies are
separate; operators must inspect their deployed responses and disclose those
cookies. No authentication or rate-limit
middleware is currently included. See [configuration](configuration.md) and
[deployment](deployment.md) when operating a public instance.
