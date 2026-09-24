# Development and testing

Follow the [quick start](../README.md), then work on `DEV`:

```sh
git switch DEV
uv sync --locked
uv run flask --app calendar_helper_ai run --host 0.0.0.0 --port 5055 --no-debugger --no-reload
```

Keep the debugger off for LAN and Tailscale testing. Restart the server after code changes because this command intentionally disables automatic reload. Changes belong on DEV; tested releases go to main. Production deployment is a separate operation.

## Offline tests

```sh
uv run python -m unittest discover -s tests -v
git diff --check
```

Tests inject fake AI clients and do not load `.env`. They cover extraction and correction routing, upload boundaries, empty results, timezone/DST export, application isolation, and packaged routes/assets. Use these tests without real credentials.

## Package verification

```sh
uv build
```

Install the wheel from `dist/` into a fresh environment and run the tests from a directory outside this checkout. This catches missing package data and accidental reliance on the source directory. The wheel contains application code, templates, and runtime assets; detailed docs and design previews remain in the repository/source distribution.

Run the production entry point locally with a macOS-compatible temporary directory:

```sh
uv run gunicorn --workers 1 --worker-class gthread --threads 2 --timeout 120 --worker-tmp-dir /tmp --bind 127.0.0.1:5056 'calendar_helper_ai:create_app()'
```

App Platform uses `/dev/shm` instead of `/tmp`. Its Python buildpack consumes the root `pyproject.toml`, `uv.lock`, and `.python-version`. Keep package-manager metadata at the repository root.

## Safari release checks

Use fictional data from the [sample guide](example_images/README.md). Live checks incur AI API usage.

1. Verify the initial view, favicon, example dialog, terms, desktop width, and narrow mobile layout. Hosted on DigitalOcean and Terms of Service must share one line.
2. Submit text, then an image. Check expected event count, dates, times, and source details.
3. Correct one event and confirm other events remain intact.
4. Download and parse the ICS before importing it anywhere. Check timezone and corrected times.
5. Exercise invalid input, reset cancellation/confirmation, and recovery from a failed correction/export.
6. Repeat core extraction, correction, export, and static-asset checks after deployment.

The dated [design implementation notes](design-system/paper-pine-2026-09/IMPLEMENTATION.md) distinguish completed checks from remaining limits. Safari responsive mode is not a substitute for physical-device or cross-browser testing.

## Maintaining documentation

Keep README focused on installing and using the app. Put architecture, API, configuration, and substantial implementation explanations in `docs`. Update source mappings when files move. New design systems get `docs/design-system/<name>-YYYY-MM/`; keep previous versions as historical references.

The two event-card image copies under `docs/example_images` and the package's `static/images` must stay identical. Private operations, account identifiers, live deployment records, support tickets, and credential references must not enter public documentation.
