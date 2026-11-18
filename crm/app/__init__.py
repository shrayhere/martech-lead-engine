import os

from flask import Flask, jsonify, redirect, request, url_for
from flask_wtf.csrf import CSRFError
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from app.extensions import csrf, db, login_manager, migrate


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):
    """Enforce referential integrity (ON DELETE CASCADE / SET NULL) on SQLite."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app(config_object="config.Config"):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "reports"), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app import models  # noqa: F401  (register models)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(error="Authentication required"), 401
        return redirect(url_for("pages.login", next=request.path))

    from app.routes import register_blueprints
    register_blueprints(app)
    _register_error_handlers(app)

    from app.cli import register_cli
    register_cli(app)
    return app


def _register_error_handlers(app):
    def wants_json():
        return request.path.startswith("/api/")

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        if wants_json():
            return jsonify(error="Invalid or missing CSRF token. Refresh the page and try again."), 400
        return e.description, 400

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(e):
        mb = app.config["MAX_UPLOAD_MB"]
        return jsonify(error=f"File is too large. Maximum upload size is {mb} MB."), 413

    @app.errorhandler(OperationalError)
    def db_unavailable(e):
        db.session.rollback()
        app.logger.exception("Database error")
        return jsonify(error="The database is unavailable or returned an error. Please try again."), 503

    @app.errorhandler(HTTPException)
    def http_error(e):
        if wants_json():
            return jsonify(error=e.description), e.code
        return e

    @app.errorhandler(Exception)
    def unhandled(e):
        db.session.rollback()
        app.logger.exception("Unhandled error")
        if wants_json():
            return jsonify(error="An unexpected server error occurred."), 500
        return "An unexpected server error occurred.", 500
