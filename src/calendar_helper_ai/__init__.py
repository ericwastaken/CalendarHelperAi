"""Calendar Helper AI application factory."""
import logging
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from openai import OpenAI

from .config import environment_config


def create_app(test_config=None):
    """Create an independently configured app for Flask, Gunicorn, or tests."""
    if test_config is None:
        load_dotenv(Path.cwd() / '.env')

    app = Flask(__name__)
    app.config.from_mapping(environment_config())
    if test_config is not None:
        app.config.update(test_config)

    logging.basicConfig(format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    app.logger.setLevel(logging.DEBUG if app.config['DEBUG_LOGGING'] else logging.INFO)
    for name, setting in (
        ('openai._base_client', 'OPENAI_HTTP_CLIENT_LEVEL'),
        ('openai._http_client', 'OPENAI_HTTP_CLIENT_LEVEL'),
        ('openai._streaming', 'OPENAI_API_LEVEL'),
    ):
        logging.getLogger(name).setLevel(getattr(logging, app.config[setting], logging.ERROR))

    client = app.config.get('OPENAI_CLIENT')
    if client is None and app.config['OPENAI_API_KEY']:
        client = OpenAI(api_key=app.config['OPENAI_API_KEY'])
    app.extensions['openai'] = client

    from .routes import bp
    app.register_blueprint(bp)
    app.logger.info('Application starting up')
    return app
