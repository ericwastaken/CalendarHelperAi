# Architecture and repository layout

Calendar Helper AI is one Flask application serving a vanilla JavaScript frontend and JSON endpoints. OpenAI handles extraction, prompt safety checks, corrections, and optional address enrichment. The `icalendar` library produces calendar files. The active workflow has no application database or user-account system.

## Layout

```text
src/calendar_helper_ai/
    __init__.py                 Application factory
    config.py                   Runtime configuration and upload limits
    routes.py                   Blueprint with page and API routes
    prompts.py                  AI prompt templates
    services/
        ai_processor.py         Extraction, corrections, date/location normalization
        calendar.py             ICS generation and timezone handling
        location.py             Legacy IP lookup helper, not called by current routes
    templates/index.html        Application shell
    static/                     CSS, JavaScript, icons, images, terms, example walkthrough
tests/                          Offline regression and package contracts
docs/                           Detailed documentation and design history
pyproject.toml                  Package metadata, dependencies, build configuration
uv.lock                         Locked dependency resolution
.python-version                 Python runtime selection
Procfile                        Production Gunicorn entry point
.do/app.yaml                    Generic creation template
```

The `src` layout separates importable code from repository tools and documentation. Install the package with `uv sync --locked`; do not rely on setting `PYTHONPATH`. Static files and templates are package data included in the wheel. Browser URLs remain `/static/...` even though the files live beneath `src`.

## Application creation

`create_app()` loads `.env` from the current working directory without replacing existing environment values, reads configuration, creates an application-owned OpenAI client when a key is supplied, and registers the route blueprint. Importing modules does not create a global Flask app or AI client. Tests pass configuration and a fake `OPENAI_CLIENT` directly and skip dotenv loading.

Each application owns its configuration and client. Flask CLI discovers `create_app`; Gunicorn uses `calendar_helper_ai:create_app()`. Application version comes from installed package metadata, maintained in `pyproject.toml`.

## Request flow

1. The browser gets upload limits and version from `/api/config`.
2. `/process` validates multipart uploads and text. It rejects more than five images, unsupported MIME types, files above 4 MiB, and requests above the 21 MiB envelope.
3. The AI service checks prompt suitability, then sends text and any image data in one extraction request to `gpt-4o`. The browser's IANA timezone and current date provide context.
4. Date normalization supplies a one-hour end time when absent. Named locations may receive AI-generated address details. This is model output, not a verified maps-directory lookup; users must review it.
5. `/correct` receives the current events and correction text from the browser, applies AI corrections, and returns updated events.
6. `/download-ics` serializes the submitted events. Aware datetimes preserve their instant; naive datetimes use the requested timezone. Events involving the repeated daylight-saving hour use UTC to retain the intended instant. Invalid time ranges fail instead of silently disappearing.

The existing IP location helper is retained for reference but is not connected to the active routes. Location prompt context defaults to unknown unless a Flask session supplies it.

## Frontend phases

The frontend moves through input, processing, review/correction, and export confirmation. Recoverable errors preserve inputs or reviewed events. Export downloads a file; it does not add events to a calendar automatically. Reset is confirmed before clearing reviewed work. Example, image-preview, terms, and reset dialogs use native browser dialogs.

Drafts, images, correction history, and results live in JavaScript memory. Refresh or closing the page clears that state. The session expires after one hour without an extension, with a warning during the last five minutes; pending operations defer expiration. The dated [design implementation](design-system/paper-pine-2026-09/IMPLEMENTATION.md) describes components and recovery behavior.

## Data handling

The application sends submitted text and images to OpenAI. It does not write appointment records to an application database. Browser downloads are saved by the user, and service providers may retain requests or logs according to their own policies. Server upload handling may spool larger multipart files to temporary storage. This is not a guarantee of memory-only processing or regulatory compliance.

Normal operation keeps debug logging off. Debug logging can include prompts and event details; use fictional data for testing. Flask session cookies are signed, not encrypted. No authentication or rate-limit middleware is currently included. See [configuration](configuration.md) and [deployment](deployment.md) when operating a public instance.
