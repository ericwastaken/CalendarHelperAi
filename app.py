import os
import logging
from flask import Flask

# Setup logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Import routes after app initialization
from routes import *