"""Calendar Helper AI application factory."""
import logging
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from openai import OpenAI

from .config import environment_config, validate_model


def create_app(test_config=None):
    """Create an independently configured app for Flask, Gunicorn, or tests."""
    if test_config is None:
        load_dotenv(Path.cwd() / '.env')

    app = Flask(__name__)
    app.config.from_mapping(environment_config())
    if test_config is not None:
        app.config.update(test_config)
    app.config['OPENAI_MODEL'] = validate_model(app.config['OPENAI_MODEL'])

    from .observability import install_logging, log_event
    install_logging(app)

    client = app.config.get('OPENAI_CLIENT')
    if client is None and app.config['OPENAI_API_KEY']:
        try:
            client = OpenAI(api_key=app.config['OPENAI_API_KEY'], timeout=45, max_retries=1)
        except Exception as error:
            # SDK initialization diagnostics can embed configuration or payloads.
            # Keep the app available with its existing generic configuration error.
            with app.app_context():
                log_event('provider_failed', logging.ERROR, stage='initialize',
                          error_type='provider_configuration', exception_class=type(error).__name__)
            client = None
    app.extensions['openai'] = client

    from .routes import bp
    app.register_blueprint(bp)
    with app.app_context():
        log_event('application_started')
    return app
