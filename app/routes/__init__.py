"""One Blueprint per feature; register_blueprints() wires them all into the app."""

from app.routes.account_security import bp as account_security_bp
from app.routes.assignment import bp as assignment_bp
from app.routes.auth import bp as auth_bp
from app.routes.categories import bp as categories_bp
from app.routes.collaboration import bp as collaboration_bp
from app.routes.custody import bp as custody_bp
from app.routes.dashboard import bp as dashboard_bp
from app.routes.evidence import bp as evidence_bp
from app.routes.handovers import bp as handovers_bp
from app.routes.lab import bp as lab_bp
from app.routes.monitoring import bp as monitoring_bp
from app.routes.notifications import bp as notifications_bp
from app.routes.pages import bp as pages_bp
from app.routes.password_reset import bp as password_reset_bp
from app.routes.reports import bp as reports_bp
from app.routes.requester import bp as requester_bp
from app.routes.settings import bp as settings_bp
from app.routes.tasks import bp as tasks_bp
from app.routes.teams import bp as teams_bp
from app.routes.users import bp as users_bp
from app.routes.verification import bp as verification_bp


def register_blueprints(app):
    app.register_blueprint(account_security_bp)
    app.register_blueprint(assignment_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(collaboration_bp)
    app.register_blueprint(custody_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(evidence_bp)
    app.register_blueprint(handovers_bp)
    app.register_blueprint(lab_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(password_reset_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(requester_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(verification_bp)
