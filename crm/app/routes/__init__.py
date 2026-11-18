from flask import jsonify

from app.utils.api import ApiError


def register_blueprints(app):
    from app.routes import (auth, companies, contacts, dashboard, data_management, imports, leads, pages,
                            reports, settings)

    for bp in (pages.bp, auth.bp, contacts.bp, companies.bp, leads.bp, imports.bp, dashboard.bp, reports.bp,
               data_management.bp, settings.bp):
        app.register_blueprint(bp)

    @app.errorhandler(ApiError)
    def handle_api_error(e):
        body = {"error": e.message}
        if e.details:
            body["details"] = e.details
        return jsonify(body), e.status
