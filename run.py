"""TaskChain entry point:  python run.py"""
import os

from app import create_app
from app.services.sla_engine import start_sla_scheduler

app = create_app()

if __name__ == "__main__":
    # The Werkzeug debugger allows arbitrary code execution, so debug mode is
    # opt-in and defaults to off. Set FLASK_DEBUG=1 for local development only.
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    # With the debugger's auto-reloader two processes start; only the one that serves requests runs the scheduler.
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_sla_scheduler()
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=debug,
    )
