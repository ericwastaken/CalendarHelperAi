# Agent instructions

These instructions apply throughout this public repository. Keep this file as
the starting guide for agents; detailed application documentation belongs in
`docs/`. Update instructions and documentation when behavior changes.

## Read first

- [README](README.md): installation, local startup and usage.
- [Architecture](docs/architecture.md): source layout, request flow and data handling.
- [Development](docs/development.md): branch workflow, tests and Safari checks.
- [Configuration](docs/configuration.md): environment variables and model selection.
- [Logging privacy](docs/logging-privacy.md) and [container logging](docs/container-logging.md): required privacy contract, collector lifecycle and complete disable instructions.
- [Deployment](docs/deployment.md): generic release and verification procedure.

Private management records are maintained separately. Account identifiers,
credential-storage references, workstation paths, live deployment specifications,
support tickets and operational history must stay out of this repository. Consult
the operator's private handoff before changing infrastructure; do not copy it here.
Never commit `.env`, credentials, submitted appointments or raw provider payloads.

## Application structure and contracts

- Python 3.11, Flask application factory `calendar_helper_ai:create_app()`, and vanilla JavaScript frontend. Install the `src` package; do not depend on `PYTHONPATH` or restore a global `main:app` entry point.
- `src/calendar_helper_ai/routes.py` validates HTTP requests; `services/ai_processor.py` handles OpenAI calls; `prompts.py` defines extraction/correction instructions. `services/events.py` normalizes events and resolves times; `services/calendar.py` generates ICS.
- `templates/` and `static/` are package data. Preserve them in installed-wheel verification, not just source-checkout testing.
- Extraction sees text and all submitted images together. Do not add a text-only suitability check that rejects a valid appointment image before the model sees it.
- Preserve distinct `timed`, `missing` and `all_day` states. Unknown times stay unknown; suggested durations require confirmation. Export must reject unresolved times and preserve timezone/DST semantics.
- The active application has no appointment database or user accounts. Browser draft state lives in memory. Do not silently add persistence, tracking or cookies.
- The container supervisor runs Gunicorn and the application's own Fluent Bit collector. Preserve the image entrypoint; a Gunicorn-only override bypasses collection and shutdown handling. DuckDB is a separate log-query tool, not an app dependency.

## Model naming and changing models

`OPENAI_MODEL` is the exact model ID passed as the `model` argument to OpenAI.
It is separate from the API key's display name, `OPENAI_API_KEY`, and the app's
release version. The current default is `gpt-4o`; preserve it unless a change is
requested. There is no automatic model discovery, fallback or per-request switch.
Both extraction and correction use the same setting.

`config.py` reads and trims the environment value when the app is created. An
unset variable uses the default; an explicit blank is invalid. IDs must start
with an ASCII letter or digit and contain only letters, digits, `.`, `_`, `:` or
`-`, up to 128 characters. This is syntax validation, not a capability or access
check. The application forwards the ID unchanged and does not resolve it to a
provider snapshot itself. Restart/recreate the process or redeploy after changing
runtime configuration. On App Platform, this is a non-secret `RUN_TIME` setting.

A compatible model may require only an environment change. Do not assume that
every syntactically valid ID works with this integration. Check current official
provider documentation and account access before selecting one. The current
implementation requires Chat Completions, system instructions, text plus image
inputs, and `response_format={"type":"json_object"}`. It reads the JSON response
from `response.choices[0].message.content`. A model requiring a different API or
output format needs code changes, not just a new environment value.

Review these locations when changing a model or its API integration:

| Location | What may need to change |
|---|---|
| `src/calendar_helper_ai/config.py`, `.env.example`, both Compose files, `.do/app.yaml` | Change defaults consistently only when requested. Preserve explicit-blank validation and runtime forwarding. An operator-only override does not require changing repository defaults. |
| `src/calendar_helper_ai/__init__.py` | Client construction, SDK configuration and retry behavior if the integration changes. |
| `src/calendar_helper_ai/services/ai_processor.py` | `call_model()` request parameters, API endpoint, timeout/error mapping and response parsing; extraction's image encoding/message format and correction message construction. Preserve the server/browser timeout budget. |
| `src/calendar_helper_ai/prompts.py` | Instructions and JSON contract if the candidate handles them differently. Keep calendar-only outcomes, missing-time rules and correction semantics. |
| `src/calendar_helper_ai/observability.py` | Approved model labels and provider usage mapping. Currently maps `prompt_tokens`, `completion_tokens` and `prompt_tokens_details.cached_tokens` to safe counters. Another response shape may require a new mapping. |
| `tests/test_model_usage.py` and relevant event/API tests | Verify both call paths, image input, JSON parsing, invalid responses, errors, missing usage and full logging disable. Add regression cases for compatibility changes. |
| `pyproject.toml`, `uv.lock` | Update the SDK only if necessary, retaining locked dependency and installed-wheel verification. |
| `docs/configuration.md`, `docs/architecture.md`, `docs/logging-privacy.md` | Keep supported request assumptions, configuration and usage accounting aligned with implementation. |

The log model allowlist is a privacy boundary, not an API allowlist. An unlisted
configured ID is still sent to OpenAI, but logs label it `other`. Add an approved
public model label with tests when useful; never log arbitrary configuration or
the provider's raw returned model string. A recognized log label does not prove
that a model is available or compatible.

Before adopting a different model, run offline tests and live local checks with
fictional text/images, corrections, missing times, suggested durations and ICS
export. Offline forwarding tests prove wiring, not real model accuracy or
availability. Verify usage counters and error handling. Live tests incur API
usage; document what was actually tested before seeking deployment approval.

## Logging and privacy

Application-controlled logs must never contain personal content: no prompts,
images, appointment fields, addresses, raw HTTP bodies, credentials or provider
exception text. Use the typed event/value allowlists in `observability.py`;
do not add free-text debugging fields or enable payload-capable SDK/access logs.
Test logging changes with fictional canaries across stdout, stderr and spool.

Emit usage once per returned provider response, before calendar-payload validation.
Missing usage is unknown, not zero. Cached input is included in input tokens;
do not add it again. Counters are diagnostic, not a complete billing ledger.
Preserve `LOGGING_ENABLED=false` as the complete application logging/collector
off switch. Hosting/provider logs and retention are separate; do not promise
lossless delivery from bounded ephemeral buffers or provider-wide data removal.

## Development and verification

Use `DEV` for application work and merge tested releases into `main`. Follow an
explicit request for a different branch workflow, including documentation-only
maintenance on `main`. Do not discard unrelated work or switch an active shared
service without checking ownership. Finish completed releases on clean `main`.

```sh
uv sync --locked
uv run python -m unittest discover -s tests -v
git diff --check
```

Tests use fake clients and require no real API key. For packaging/runtime changes,
also build with `uv build`, install the wheel with locked dependencies into a
fresh environment, and test outside the checkout. For collector changes, test
the supervised container with logging enabled and completely disabled.
Documentation-only edits need link, accuracy and diff checks, not live AI calls.

Use four-space indentation and preserve the existing Python style, including
two blank lines before function and method definitions. Keep local development
bound to `0.0.0.0` when network testing is intended, with the debugger disabled.
Check existing listeners and containers before starting or replacing processes.

Preserve the narrow responsive UI and sticky brand/version/Example/phase header.
Hosted-on and Terms links share a row. Consult `docs/design-system/` before UI
changes; new systems use `<name>-YYYY-MM` directories. Keep the sample event-card
copies in `docs/example_images/` and packaged `static/images/` identical. Use
Safari for the documented browser checks unless instructed otherwise.

## Releases and documentation

For an application release, bump `[project].version` in `pyproject.toml`, refresh
`uv.lock`, and verify installed metadata drives both `/api/config` and the visible
version. Do not duplicate version strings. Documentation-only maintenance does
not require an application release, version bump or deployment.

Commit/push and production deployment are separate actions. Obtain authorization
for the intended deployment. Preserve existing secrets, domains, capacity,
readiness and sleep settings; never replace a live spec with the generic creation
template's empty secrets. Verify the exact deployed commit, HTTPS, version,
assets, actual workflows and log delivery. Keep deployment evidence private.

Keep README focused on clone/install/use and links to deeper docs. Update related
configuration, architecture, API, privacy and deployment docs with behavioral
changes. Record verification limits honestly; a successful build or healthy
deployment alone does not establish complete application behavior.
