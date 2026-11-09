# Container runtime and logging

Version 1.2.0 adds an application-owned Fluent Bit collector. A single image runs
one Gunicorn worker with two threads and Fluent Bit 5.1.5, managed by a Python
supervisor under tini. The Mac needs Docker and, optionally, a separate DuckDB
workspace. It does not need Fluent Bit installed on the host.

## Data flow

The app's allowlisted JSON operational events go to stdout and a rotating file at
`/logs/spool/events.jsonl`. Fluent Bit tails the file, adds deployment identity and
writes JSONL to the selected output. It does not ingest stdout a second time.
Gunicorn and dependency diagnostics remain on platform stdout/stderr and are not
archived by this pipeline. User images, prompts, event content, IP addresses,
credentials and raw exception messages are excluded from operational events.

Each event has a unique `event_id`; related events share `request_id`. Deduplicate
by event ID, never request ID. `schema_version` is 1. Collector identity includes
`project`, `environment`, `service` and `instance`.

The file handler assumes one Gunicorn worker. Threads share its lock. Do not raise
worker count without replacing the spool with a multiprocess-safe transport.

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
