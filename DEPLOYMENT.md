# Deploying to DigitalOcean App Platform

CalendarHelperAI runs its Flask frontend and API as one web service. Python 3.11 is pinned in `.python-version`; dependencies are defined in `pyproject.toml` and locked in `uv.lock`.

This public guide describes reproducible setup. Account identifiers, live deployment records, DNS change history, support requests, billing details and credential-storage locations belong in private operational documentation.

## Configure a service

1. Connect your GitHub repository to DigitalOcean App Platform.
2. Use [`.do/app.yaml`](.do/app.yaml) as a creation template. Adjust the repository, branch, region and instance size for your deployment. The template selects `main` and disables automatic deployment on push.
3. Set `OPENAI_API_KEY` and `FLASK_SECRET_KEY` as encrypted runtime environment variables. The template contains empty placeholders; supply your own values through the provider's secret configuration.
4. Use the Gunicorn command from [`Procfile`](Procfile). The service listens on the provider's `PORT` environment variable. The template uses port 8080, one worker and two threads. `/dev/shm` is the Linux container's worker temporary directory.
5. Configure any custom domains in App Platform and follow the provider's current DNS instructions. Wait for trusted HTTPS to work before directing users to a new hostname.
6. Deploy the intended commit and perform the checks below.

Keep these runtime settings for normal operation:

```text
DEBUG_LOGGING=false
DEBUG_LOG_IMAGE=false
OPENAI_HTTP_CLIENT_LEVEL=ERROR
OPENAI_API_LEVEL=ERROR
```

Keep `.env`, credentials, private operational records and exported specifications containing secrets out of Git. `SESSION_SECRET` is not used by this application; Flask uses `FLASK_SECRET_KEY`.

## Update an existing service

Review and merge the intended changes before deploying. Preserve existing encrypted secrets, domain bindings and other service settings when updating the live specification. The checked-in creation template omits custom domains and has empty secret values, so it is not a complete replacement for an existing service's specification.

Choose instance capacity based on measured memory use and expected concurrency. Consult current provider pricing and feature eligibility before changing service size or enabling optional sleep behavior.

## Validate a deployment

- Confirm the deployed branch and commit, healthy instances and successful startup logs.
- Check `/` and `/api/config`, including the expected application version and `debug_logging: false`.
- Confirm JavaScript and CSS load, and HTTPS works on every configured hostname.
- Process a synthetic image and a text-only request, review the extracted events, apply a correction and download an ICS file.
- Inspect exported dates and timezones before importing into a calendar.
- Check error recovery and resource use with representative inputs. Live extraction tests incur AI API usage.

The [sample image guide](docs/example_images/README.md) provides fictional events for testing. The [design implementation notes](docs/design-system/paper-pine-2026-09/IMPLEMENTATION.md) record local UI validation and its limits. Neither substitutes for checks on a newly deployed release.

The application does not include authentication or an access gate. Account for its public processing endpoints when configuring access and usage limits.

## References

- [Python buildpack](https://docs.digitalocean.com/products/app-platform/reference/buildpacks/python/)
- [App specification](https://docs.digitalocean.com/products/app-platform/reference/app-spec/)
- [Custom domains](https://docs.digitalocean.com/products/app-platform/how-to/manage-domains/)
- [Pricing](https://docs.digitalocean.com/products/app-platform/details/pricing/)
