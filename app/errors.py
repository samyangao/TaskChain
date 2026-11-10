"""Central error handlers: database and HTTP errors never leak driver messages or stack traces."""

import psycopg
from flask import request

from app.log import logger
from app.utils import json_error


def handle_db_error(exc):
    logger.exception("Database error: %s", type(exc).__name__)
    return json_error("A database error occurred. Please try again.", 500)


def handle_bad_uuid(exc):
    return json_error("Invalid identifier format.", 400)


def handle_404(exc):
    if request.path.startswith("/api/") or request.path == "/api":
        return json_error("Not found.", 404)
    return json_error("Page not found.", 404)


def handle_413(exc):
    return json_error("That file is too large (8 MB maximum).", 413)


def handle_unexpected(exc):
    from werkzeug.exceptions import HTTPException
    if isinstance(exc, HTTPException):
        return json_error(exc.description or exc.name, exc.code or 500)
    logger.exception("Unhandled application error")
    return json_error("Something went wrong on the server.", 500)


def register_error_handlers(app):
    app.register_error_handler(psycopg.Error, handle_db_error)
    app.register_error_handler(psycopg.errors.InvalidTextRepresentation, handle_bad_uuid)
    app.register_error_handler(404, handle_404)
    app.register_error_handler(413, handle_413)
    app.register_error_handler(Exception, handle_unexpected)
