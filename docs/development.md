# Development and testing

Follow the [quick start](../README.md), then work on `DEV`:

```sh
git switch DEV
uv sync --locked
uv run flask --app calendar_helper_ai run --host 0.0.0.0 --port 5055 --no-debugger --no-reload
```

Keep the debugger off for LAN and Tailscale testing. Restart the server after code changes because this command intentionally disables automatic reload. Changes belong on DEV; tested releases go to main. Production deployment is a separate operation.

## Container development

Use the application-owned collector through Compose as described in [container logging](container-logging.md). Set a dedicated `APP_LOG_DIR` for the standard Compose file. The standalone
`compose.logging-disabled.yaml` requires no log directory. Native Flask/Gunicorn runs above remain available, but do not include Fluent Bit.

## Offline tests

```sh
uv run python -m unittest discover -s tests -v
git diff --check
```

Tests inject fake AI clients and do not load `.env`. They cover extraction and correction routing, upload boundaries, empty results, timezone/DST export, application isolation, and packaged routes/assets. Use these tests without real credentials.

Model/usage tests exercise the real SDK through an offline HTTP transport. They
verify `OPENAI_MODEL` forwarding for images and corrections, bounded token counts,
rejected-response usage, missing metadata, unlisted model privacy and full logging
disable. An override passing offline tests proves wiring, not the alternate
model's real availability or accuracy; a real model change needs local fixtures.

## Package verification

```sh
uv build
```

Install the wheel from `dist/` into a fresh environment using the locked dependencies,
then run the tests from a directory outside this checkout. Export those dependencies
with `uv export --frozen --no-dev --no-emit-project --format requirements-txt` and
pass the resulting requirements file to the installer alongside the wheel.
Unconstrained wheel installation can select a different SDK generation and is not
the verified runtime. This catches missing package data and accidental reliance on the source directory. The wheel contains application code, templates, and runtime assets; detailed docs and design previews remain in the repository/source distribution.

Run the production entry point locally with a macOS-compatible temporary directory:

```sh
uv run gunicorn --access-logfile /dev/null --error-logfile /dev/null --workers 1 --worker-class gthread --threads 2 --timeout 120 --worker-tmp-dir /tmp --bind 127.0.0.1:5056 'calendar_helper_ai:create_app()'
```

The container also uses `/tmp`; its Dockerfile installs locked dependencies from
root packaging metadata. The command above exercises Gunicorn alone. Use Compose
to test the complete supervised application and collector runtime.

## Safari release checks

Use fictional data from the [sample guide](example_images/README.md). Live checks incur AI API usage.

1. Verify the initial view, favicon, example dialog, terms, desktop width, and narrow mobile layout. Hosted on DigitalOcean and Terms of Service must share one line.
2. Submit text, then an image. Check expected event count, dates, times, and source details.
3. Correct one event and confirm other events remain intact.
4. Download and parse the ICS before importing it anywhere. Check timezone and corrected times.
5. Exercise invalid input, reset cancellation/confirmation, and recovery from a failed correction/export.
6. Test a date-only appointment: export stays disabled until its time is set or an all-day reminder is chosen. Check real midnight remains timed, and a missing end time requires confirmation of its suggested duration. Verify date-only ICS values and exclusive end dates.
7. Simulate provider authentication, quota, connection, timeout and malformed-response errors offline; verify reference IDs and payload-free logs.
8. Repeat core extraction, correction, export, and static-asset checks after deployment.

The dated [design implementation notes](design-system/paper-pine-2026-09/IMPLEMENTATION.md) distinguish completed checks from remaining limits. Safari responsive mode is not a substitute for physical-device or cross-browser testing.

## Maintaining documentation

Keep README focused on installing and using the app. Put architecture, API, configuration, and substantial implementation explanations in `docs`. Update source mappings when files move. New design systems get `docs/design-system/<name>-YYYY-MM/`; keep previous versions as historical references.

The two event-card image copies under `docs/example_images` and the package's `static/images` must stay identical. Private operations, account identifiers, live deployment records, support tickets, and credential references must not enter public documentation.


## Logging change review

Changes to routes, AI clients, logging or the process runtime must preserve the
[privacy contract](logging-privacy.md). Use fictional canaries to check stdout,
stderr and spool files, including the real SDK with an offline HTTP transport.
Test enabled file output and disabled container behavior without S3 credentials.
Review configuration defaults, both Compose files, Dockerfile, creation template
and docs together. A new event/field must pass a privacy review and have tests;
never add free-text fields as a debugging shortcut. A changed deployment still
needs production delivery checks.
