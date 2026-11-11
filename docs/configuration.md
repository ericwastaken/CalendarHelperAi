# Configuration

Container logging is configured separately from application behavior. See
[container logging](container-logging.md) for `LOG_OUTPUT`, environment identity,
S3 destinations and secret injection. `APP_LOG_FILE` optionally enables the
allowlisted rotating operational spool; the container fixes it to
`/logs/spool/events.jsonl`. Native runs retain stdout-only operational logging by default.
`LOGGING_ENABLED=false` disables application operational output and, in the
container, the collector and its writes/uploads. Restart or redeploy to apply it.
See [full disable instructions](container-logging.md#disable-logging-completely)
and the [logging privacy contract](logging-privacy.md).

Runtime values come from the process environment. A local `.env` in the launch directory is loaded by the factory without overriding existing environment variables. `.env` is ignored by Git; `.env.example` contains blank placeholders only. Never commit credentials or exported live app specifications.

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | None | Required for real extraction and corrections; not needed to serve the UI or run offline tests |
| `OPENAI_MODEL` | `gpt-4o` | Model ID for both extraction and corrections; non-secret runtime setting |
| `FLASK_SECRET_KEY` | Random per application instance | Flask cookie-signing key; set a stable random secret for deployment |
| `LOGGING_ENABLED` | `true` | Master operational logging switch; accepts only true/false, case-insensitive; false disables stdout, spool and container collector |
| `DEBUG_LOGGING` | `false` | Legacy runtime flag exposed in config; does not enable payload diagnostics or disable operational logging |
| `OPENAI_HTTP_CLIENT_LEVEL` | `ERROR` | Deprecated compatibility value, ignored; dependency diagnostics are suppressed |
| `OPENAI_API_LEVEL` | `ERROR` | Deprecated compatibility value, ignored; dependency diagnostics are suppressed |
| `PORT` | Supplied by hosting provider | Gunicorn bind port in the production command |

Configure secrets and logging flags with `RUN_TIME` scope on App Platform. `SESSION_SECRET` is not read. `DEBUG_LOG_IMAGE` is a legacy setting with no active code path; it may remain false in older deployment specifications.

`config.py` defines a 4 MiB limit per image, supported JPEG/PNG/TIFF MIME types, and a 21 MiB total request envelope. The route enforces five images; `/api/config` exposes per-file size, MIME types, installed package version, and the application's runtime debug flag.

`pyproject.toml` is the source of truth for the release version. Re-run `uv lock` and `uv sync --locked` after changing metadata or dependencies. The default AI model remains `gpt-4o`. Provider calls have a 45-second timeout and at most one SDK retry, within the 120-second server/browser request budget.

## Selecting a model

Set `OPENAI_MODEL` in the process environment, local `.env`, or DigitalOcean's
non-secret `RUN_TIME` configuration. Both Compose variants pass it into the
container. Unset means `gpt-4o`; explicitly empty values fail startup. Surrounding
environment whitespace is trimmed. IDs must start with an ASCII letter/digit and
contain only ASCII letters/digits, periods, underscores, colons or hyphens, up to
128 characters. Invalid values are never echoed in the error. Changing the setting
requires restarting the process or recreating/redeploying the container.

The ID is forwarded to OpenAI without a hardcoded model availability list. It must
be available to your API project and support Chat Completions, image inputs,
system instructions and `response_format={"type":"json_object"}`. Configuration
validation checks syntax, not provider availability or extraction quality. Models
requiring a different endpoint or request shape need a code change. No automatic
fallback or model switching is performed.

Before selecting a different model, test representative images, terse text,
missing times, corrections and ICS export locally. Setting a valid ID does not
guarantee equivalent calendar accuracy. Keep `gpt-4o` until that comparison passes.
The log model label uses a finite approved list; other IDs (including unlisted
snapshots) are logged as `other`, never copied verbatim from configuration or a
provider response. See [usage accounting](logging-privacy.md#token-usage-accounting).

Tests can call `create_app({...})` with `TESTING`, `SECRET_KEY`, `OPENAI_API_KEY`, and `OPENAI_CLIENT`. Supplying a test mapping skips dotenv loading. Use a fake client and explicitly set `OPENAI_API_KEY` to `None` for offline tests.
