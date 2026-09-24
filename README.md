# Calendar Helper AI

Turn photos, schedules, and notes into calendar events. Review the results, ask for corrections, and download an `.ics` file for your calendar app.

[Use the hosted app](https://calendarhelperai.com) or run it locally. The interface stays narrow on desktop and adapts to mobile screens.

## Clone and install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
git clone https://github.com/ericwastaken/CalendarHelperAi.git
cd CalendarHelperAi
uv sync --locked
cp .env.example .env
```

Python 3.11 is selected by `.python-version`. Add your `OPENAI_API_KEY` and a random `FLASK_SECRET_KEY` to the ignored `.env` file. Generate the signing key with:

```sh
uv run python -c 'import secrets; print(secrets.token_hex(32))'
```

## Run locally

```sh
uv run flask --app calendar_helper_ai run --host 0.0.0.0 --port 5055 --no-debugger --no-reload
```

Open http://127.0.0.1:5055. Other devices can use your computer's LAN or Tailscale IPv4 address with port `5055`. Only expose the development server on trusted networks; the app has no login gate. Live processing uses your OpenAI API account.

## Use the app

1. Choose up to five images, each no larger than 4 MiB, or enter event details as text.
2. Select **Find my events** and check the dates, times, and locations.
3. Enter any corrections, then select **Download calendar file**.
4. Open or import the downloaded file in your calendar app and confirm the destination calendar.

The **Example** button includes a sample photo and walkthrough. More fictional fixtures are in the [sample image guide](docs/example_images/README.md).

## Test

```sh
uv run python -m unittest discover -s tests -v
```

The automated tests use fake AI clients and make no external API calls. See [development](docs/development.md) for the DEV workflow and package verification.

## Documentation

- [Documentation index](docs/README.md)
- [Architecture and repository layout](docs/architecture.md)
- [API](docs/api.md) and [configuration](docs/configuration.md)
- [Development and testing](docs/development.md)
- [DigitalOcean deployment](docs/deployment.md)
- [Design systems](docs/design-system/README.md)

Licensed under the [MIT License](LICENSE).
