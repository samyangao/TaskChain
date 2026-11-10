"""TaskChain application package. Use create_app() to build the Flask app."""

from flask import Flask

from app.config import FLASK_CONFIG, FRONTEND_DIR, load_secret_key
from app.errors import register_error_handlers
from app.hooks import register_hooks
from app.log import configure_logging
from app.routes import register_blueprints


def create_app():
    app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="/static")
    app.secret_key = load_secret_key()
    app.config.update(FLASK_CONFIG)
    configure_logging()
    app.logger  # initialise the shared "app" logger before background threads use it
    register_error_handlers(app)
    register_hooks(app)
    register_blueprints(app)
    return app
