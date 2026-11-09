# Container runtime and logging

Version 1.2.0 adds an application-owned Fluent Bit collector. A single image runs
one Gunicorn worker with two threads and Fluent Bit 5.1.5, managed by a Python
supervisor under tini. Version 1.2.1 adds a complete off switch and stronger
privacy enforcement. The Mac needs Docker and, optionally, a separate DuckDB
workspace. It does not need Fluent Bit installed on the host.

## Data flow

The app's allowlisted JSON operational events go to stdout and a rotating file at
`/logs/spool/events.jsonl`. Fluent Bit tails the file, adds deployment identity and
writes JSONL to the selected output. It does not ingest stdout a second time.
Gunicorn access/error logs and payload-capable dependency diagnostics are
suppressed. Collector/supervisor infrastructure diagnostics are separate from the
archive. Personal content must never enter application operational logs: images,
prompts, event content, IP addresses, credentials and raw exception messages are
excluded. Read the [privacy contract](logging-privacy.md) for enforcement, the
complete schema and the boundary with provider-controlled logs.

Each event has a unique `event_id`; related events share `request_id`. Deduplicate
by event ID, never request ID. `schema_version` is 1. Collector identity includes
`project`, `environment`, `service` and `instance`.

The file handler assumes one Gunicorn worker. Threads share its lock. Do not raise
worker count without replacing the spool with a multiprocess-safe transport.

## Modes and defaults

| Mode | Application stdout | Operational spool | Fluent Bit | Destination |
|---|---|---|---|---|
| Native, defaults | Validated JSON | None | None | Console only |
| Native, `APP_LOG_FILE` set | Validated JSON | Selected file | None | File plus console |
| Standard Compose | Validated JSON | `/logs/spool/events.jsonl` | In app container | Local hourly JSONL |
| Container, `LOG_OUTPUT=s3` | Validated JSON | Same spool | In app container | Private gzip JSONL objects |
| `LOGGING_ENABLED=false` | None | None | Not started | None |

`LOGGING_ENABLED` accepts true/false case-insensitively; other values fail startup.
Set it in the process environment before launch. Changing `.env` does not alter
an already-running process. `DEBUG_LOGGING=false` is not an off switch, and
clearing `APP_LOG_FILE` alone only disables a native run's file copy.

## Disable logging completely

For a local container with no log bind mount or cloud configuration:

```sh
docker compose -f compose.logging-disabled.yaml up --build -d
```

This is a standalone Compose file, not an override to merge with `compose.yaml`.
It uses `LOGGING_ENABLED=false` and requires no `APP_LOG_DIR` or S3 credentials.
Use the same `-f` argument when stopping it. Stop an existing app on the same
host port first; do not start a second conflicting container.

For any existing container deployment, set the runtime environment variable
`LOGGING_ENABLED=false` and recreate/redeploy the container. Keep the supplied
entrypoint. It skips collector configuration/startup, log directories, spool
writes and uploads. Health metadata under `/tmp/runtime` remains so readiness
can check the application process. Request IDs and normal application behavior
remain available. Gunicorn output is discarded in this mode. A constant fatal
startup diagnostic and process exit status may still indicate invalid runtime
configuration; these are not request logs.

For a native development run:

```sh
LOGGING_ENABLED=false uv run flask --app calendar_helper_ai run \
    --host 0.0.0.0 --port 5055 --no-debugger --no-reload
```

For a native production server, also disable that server's access/error logs:

```sh
LOGGING_ENABLED=false uv run gunicorn --access-logfile /dev/null \
    --error-logfile /dev/null --bind 127.0.0.1:5055 \
    'calendar_helper_ai:create_app()'
```

A native CLI may still print a startup banner. The app cannot silence arbitrary
external servers or hosting/CDN logs. Remove unused S3 writer credentials from
the app configuration after disabling shipping. Existing log files, collector
buffers, remote objects, snapshots and exports are not deleted by the switch.
Delete or expire them separately if desired. Re-enabling with old collector state
may resume pending uploads; remove only this deployment's old buffers first if
that is not intended.

Verify a fresh disabled container without S3 credentials: `/api/config` succeeds,
its readiness metadata lists only the app, no Fluent Bit process exists, and
`/logs` has no generated files. Send a fictional invalid request; it still returns
400 with an `X-Request-ID`, but creates no operational records or uploads.
For an existing mount, compare file timestamps/sizes before and after instead of
expecting historical files to disappear. With logging off, diagnose problems via
HTTP results, health and process exit status.

## Development

Set `APP_LOG_DIR` to a dedicated directory for this project's dev environment.
Compose bind mounts it at `/logs`, including spool, collector state and output.
The container runs as UID 10001; on Linux prepare ownership accordingly. Docker
Desktop must be allowed to share the selected host directory.

```sh
export APP_LOG_DIR="/absolute/path/to/project/dev/logs"
export LOG_INSTANCE="my-machine"
mkdir -p "$APP_LOG_DIR"
docker compose up --build -d
docker compose logs --tail 30
docker compose down
```

Host port defaults to 5055 on all interfaces; set `APP_HOST_PORT` if occupied.
`LOG_OUTPUT=file` is fixed by the dev Compose definition. Dev requires no S3 key.
Files in `output/` contain collected records; `spool/` and `state/` support restart
recovery. Keep all active files, databases and buffers out of file synchronization.
Copy finalized batches to an archive directory if synchronization is desired.
Stopping a DuckDB UI has no effect on log capture.

Input spool files rotate at 1 MiB with ten backups. Collected output uses UTC
hourly filenames and is not automatically deleted. Retention requires a separate
policy. The spool is a bounded operational buffer: an extended collector outage
can exceed its capacity and overwrite its oldest buffered records. File output's
retry queue and S3's separate buffer are capped at 64 MB. Monitor failures and
disk capacity rather than assuming lossless delivery.

## Production routing

Use the same Dockerfile and supervisor. Supply these runtime settings:

| Setting | Purpose |
|---|---|
| `LOGGING_ENABLED` | true (default) or false; master switch, independent of destination |
| `LOG_PROJECT` | Project identifier, default calendarhelperai |
| `LOG_ENV` | prod, dev or an explicitly isolated test environment |
| `LOG_OUTPUT` | file or s3 |
| `LOG_INSTANCE` | Optional stable instance label; defaults to container hostname |
| `LOG_S3_BUCKET` | Destination bucket |
| `LOG_S3_ENDPOINT` | HTTPS S3-compatible endpoint |
| `LOG_S3_REGION` | Signing region required by the provider |
| `LOG_S3_PREFIX` | Project/environment key prefix, without credentials |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Scoped writer credentials, injected as runtime secrets |

S3 output uses gzip JSONL, UTC date paths, unique object names, PutObject and a
five-second upload timeout for sparse traffic. Timeout is a batching target, not
a delivery SLA. Different S3-compatible providers need endpoint/signing tests.
Use separate read-only credentials for querying. Provider permission models may
scope only to a whole bucket rather than a project prefix; document that boundary.

The supervisor restarts a failed collector up to three times per rolling minute.
Repeated failure stops the app/container visibly instead of silently continuing
without a collector. Shutdown drains Gunicorn first (up to 22 seconds), allows
Tail two seconds to catch up, then gives Fluent Bit up to 15 seconds to flush.
Configure at least 45 seconds for container stop where the platform allows it.
Actual platform termination behavior must be tested during deployment.

App Platform disk is ephemeral. Abrupt loss can discard records not yet uploaded,
even with filesystem buffering. This pipeline is diagnostic logging, not a
lossless audit ledger. Verify S3 object arrival: Fluent Bit's ordinary output
success counters do not accurately represent the S3 plugin's independent uploads.
The S3 internal retry limit is explicitly 1,000; exhausted chunks are quarantined
with a separate 64 MB cap. Quarantine is not automatically replayed. Inspect and
recover it before ephemeral storage is destroyed; exceeding its cap loses further
exhausted chunks. Credentials and endpoint failures must be corrected promptly.

## Verification

Run the installed-package regression suite inside the image:

```sh
docker run --rm --entrypoint python -e APP_LOG_FILE= calendarhelperai:dev \
    -m unittest discover -s tests -v
```

`container/sample_logs.py` emits fictional events, including success, rejection,
rate limit and timeout cases. Run only in a disposable local test container with
an isolated destination. Verify local files and remote objects, distinct event
IDs, correlated requests, collector restart, rotation, graceful stop, bad
credentials, empty data and network failure. Re-query the same data through
DuckDB and verify counts/search results. Do not use production inputs as fixtures.

Validate both local ARM64 and deployment AMD64 builds. Measure total memory with
the application and collector under representative requests. Deployment approval,
scale-to-zero behavior and provider-side durability checks are separate from
local success.


## Querying logs independently

DuckDB is optional and runs outside the app container. It can read collected
newline-delimited JSON, including gzip objects copied from a private bucket.
For a completed local batch, use this SQL in the DuckDB CLI or UI:

```sql
CREATE OR REPLACE TEMP VIEW app_logs AS
SELECT * FROM read_json_auto(
    '/absolute/path/to/output/events-*.jsonl',
    format='newline_delimited', union_by_name=true
)
QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY timestamp) = 1;

SELECT stage, status, count(*) AS requests, round(avg(elapsed_ms)) AS average_ms
FROM app_logs
WHERE event = 'request_finished'
GROUP BY stage, status
ORDER BY stage, status;

SELECT timestamp, request_id, event, stage, status
FROM app_logs
WHERE level IN ('WARNING', 'ERROR')
ORDER BY timestamp DESC;
```

Use immutable complete batches or an atomic local snapshot to avoid reading an
unfinished JSONL line. An empty file selection needs an empty-schema view in a
query workspace; the raw example expects at least one nonempty batch. Production
objects use `<project>/<environment>/YYYY/MM/DD/HH/MM/SS-<uuid>.jsonl.gz` paths.
Filter by project/environment and date before downloading or querying. Use a
separate read-only credential and keep it out of SQL history and notebooks.

DuckDB supports direct S3 reads with its `httpfs` extension and temporary secrets.
An external query workspace may instead fetch objects manually into local
snapshots, then rerun notebook queries. A snapshot does not refresh itself, and
stopping the local UI does not stop the application's collector. This repository
does not install a DuckDB service, UI notebooks, host collector or refresh job.

See DuckDB's [JSON reader](https://duckdb.org/docs/2.0/data/json/overview) and
[S3 authentication](https://duckdb.org/docs/2.0/core_extensions/httpfs/s3api)
references for your installed version. Keep saved notebooks per project and
environment in your own workspace, with request, error and recent-event queries.

## Retention and rollout checklist

No automatic retention or deletion policy is included. Configure bucket lifecycle
rules and local-file retention to suit the deployment; include query snapshots,
exports and backups in that policy. Grant the app only the bucket permissions it
needs and keep buckets private. Reader access should not permit uploads/deletion.

For every logging change, run privacy and runtime tests, exercise file output and
off mode locally, and check the documented defaults against Dockerfile, both
Compose files, configuration code and the provider creation template. After an
authorized deployment, verify version, health, synthetic request correlation,
private object arrival and field privacy. Test actual sleep/shutdown when that
feature is enabled; local drain success is not proof of cloud final-buffer delivery.
