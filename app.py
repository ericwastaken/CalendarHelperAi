import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask

# Load environment variables from .env file
load_dotenv()

# Setup console logging
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
))
logging.basicConfig(
    level=logging.DEBUG if os.environ.get('DEBUG_LOGGING', 'false').lower() == 'true' else logging.INFO,
    handlers=[handler]
)

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Import routes after app initialization
logging.info("Application starting up")
from routes import *