# Deploying to DigitalOcean App Platform

CalendarHelperAI runs its Flask frontend and API as one web service. Python 3.11 is pinned in `.python-version`; dependencies are defined in `pyproject.toml` and locked in `uv.lock`.

This public guide describes reproducible setup. Account identifiers, live deployment records, DNS change history, support requests, billing details and credential-storage locations belong in private operational documentation.

The Dockerfile installs the project and locked dependencies using uv and packages Fluent Bit with the application. The image entrypoint supervises both processes. The wheel includes Flask templates and static assets. Keep `source_dir: /` so packaging metadata remains visible. The Gunicorn target is `calendar_helper_ai:create_app()`; do not restore the former `main:app` target.

## Configure a service

1. Connect your GitHub repository to DigitalOcean App Platform.
2. Use [`.do/app.yaml`](../.do/app.yaml) as a creation template. Adjust the repository, branch, region and instance size for your deployment. The template selects `main` and disables automatic deployment on push.
3. Set `OPENAI_API_KEY` and `FLASK_SECRET_KEY` as encrypted runtime environment variables. The template contains empty placeholders; supply your own values through the provider's secret configuration.
4. Select `Dockerfile` and leave the provider run-command override empty so the image entrypoint starts the supervisor. Configure the runtime S3 settings and scoped writer credentials in [container logging](container-logging.md). The service uses `PORT`, one Gunicorn worker, two threads and `/tmp` for worker temporary files. `/api/config` is the HTTP readiness endpoint.
5. Configure any custom domains in App Platform and follow the provider's current DNS instructions. Wait for trusted HTTPS to work before directing users to a new hostname.
6. Deploy the intended commit and perform the checks below.

Keep these runtime settings for normal operation:

```text
LOGGING_ENABLED=true
DEBUG_LOGGING=false
DEBUG_LOG_IMAGE=false
OPENAI_HTTP_CLIENT_LEVEL=ERROR
OPENAI_API_LEVEL=ERROR
```

Keep `.env`, credentials, private operational records and exported specifications containing secrets out of Git. `SESSION_SECRET` is not used by this application; Flask uses `FLASK_SECRET_KEY`.

## Release procedure

1. Increase `[project].version` in `pyproject.toml` before each release. Use a patch for fixes, a minor version for compatible features, or a major version for a substantial milestone or breaking changes. The logging privacy and full-disable patch is **v1.2.1**.
2. Run `uv lock` and `uv sync --locked`. The installed package version drives both `/api/config` and the small version label below the app title; never edit separate version strings in HTML or Python. Versioned CSS/JavaScript/icon URLs refresh assets on release.
3. Run the offline suite, build and verify the package, and exercise the local Safari workflow described in [development](development.md).
4. Commit the release on DEV and merge the tested changes into main. Push the intended source commit before requesting deployment.
5. Obtain deployment approval where required, then deploy that commit with the supervised container entrypoint and preserved runtime secrets and domains. Automatic deployment is disabled in the template.
6. Confirm the deployed commit, then verify the visible version and `/api/config` match the intended release. Perform the production checks below. Record private operational results outside this public repo.

## Update an existing service

Review and merge the intended changes before deploying. Preserve existing encrypted secrets, domain bindings and other service settings when updating the live specification. The checked-in creation template omits custom domains and has empty secret values, so it is not a complete replacement for an existing service's specification.

When migrating from the Python buildpack, remove `environment_slug` and the old Gunicorn-only `run_command`, add `dockerfile_path`, and retain all other live settings, including readiness and any scale-to-zero timeout. Validate the proposed full spec before applying it. Local container success does not authorize production deployment.

Choose instance capacity based on measured memory use and expected concurrency. Consult current provider pricing and feature eligibility before changing service size or enabling optional sleep behavior.

## Validate a deployment

- Confirm the deployed branch and commit, healthy instances and successful startup logs.
- Check `/` and `/api/config`, including the expected application version and `debug_logging: false`.
- Confirm JavaScript and CSS load, and HTTPS works on every configured hostname.
- Process a synthetic image and a text-only request, review the extracted events, apply a correction and download an ICS file.
- Inspect exported dates and timezones before importing into a calendar.
- With logging enabled, correlate synthetic request IDs in private output files or S3 objects, verify fields against the privacy schema and check collector failures. With logging disabled, verify no collector, application log writes or uploads; health and request IDs must still work.
- If scale to zero is enabled, observe actual sleep and subsequent wake. A configured timeout or healthy deployment alone does not prove sleep or final-buffer delivery.
- Check error recovery and resource use with representative inputs. Live extraction tests incur AI API usage.

The [sample image guide](example_images/README.md) provides fictional events for testing. The [design implementation notes](design-system/paper-pine-2026-09/IMPLEMENTATION.md) record local UI validation and its limits. Neither substitutes for checks on a newly deployed release.

The application does not include authentication or an access gate. Account for its public processing endpoints when configuring access and usage limits.

## References

- [Python buildpack](https://docs.digitalocean.com/products/app-platform/reference/buildpacks/python/)
- [App specification](https://docs.digitalocean.com/products/app-platform/reference/app-spec/)
- [Custom domains](https://docs.digitalocean.com/products/app-platform/how-to/manage-domains/)
- [Pricing](https://docs.digitalocean.com/products/app-platform/details/pricing/)


## Disable application logging

Set `LOGGING_ENABLED=false` with `RUN_TIME` scope and redeploy the same entrypoint.
The app runs without Fluent Bit; S3 destination settings and writer credentials
are no longer required and can be removed from this service. Preserve unrelated
secrets and live configuration. Follow the [complete disable and verification
procedure](container-logging.md#disable-logging-completely). Existing log objects
are retained until explicitly deleted or expired; hosting-provider logs are
controlled separately.
