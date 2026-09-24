# Configuration

Runtime values come from the process environment. A local `.env` in the launch directory is loaded by the factory without overriding existing environment variables. `.env` is ignored by Git; `.env.example` contains blank placeholders only. Never commit credentials or exported live app specifications.

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | None | Required for real extraction and corrections; not needed to serve the UI or run offline tests |
| `FLASK_SECRET_KEY` | Random per application instance | Flask cookie-signing key; set a stable random secret for deployment |
| `DEBUG_LOGGING` | `false` | Enables application debug logging, which may contain prompts and event data |
| `OPENAI_HTTP_CLIENT_LEVEL` | `ERROR` | OpenAI client/base-client log level |
| `OPENAI_API_LEVEL` | `ERROR` | OpenAI streaming log level |
| `PORT` | Supplied by hosting provider | Gunicorn bind port in the production command |

Configure secrets and logging flags with `RUN_TIME` scope on App Platform. `SESSION_SECRET` is not read. `DEBUG_LOG_IMAGE` is a legacy setting with no active code path; it may remain false in older deployment specifications.

`config.py` defines a 4 MiB limit per image, supported JPEG/PNG/TIFF MIME types, and a 21 MiB total request envelope. The route enforces five images; `/api/config` exposes per-file size, MIME types, installed package version, and the application's runtime debug flag.

`pyproject.toml` is the source of truth for the release version. Re-run `uv lock` and `uv sync --locked` after changing metadata or dependencies. The AI model remains `gpt-4o`.

Tests can call `create_app({...})` with `TESTING`, `SECRET_KEY`, `OPENAI_API_KEY`, and `OPENAI_CLIENT`. Supplying a test mapping skips dotenv loading. Use a fake client and explicitly set `OPENAI_API_KEY` to `None` for offline tests.
