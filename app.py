from flask import Blueprint, Flask, render_template
from flask_wtf import CSRFProtect

import config
from auth import login_required
from auth.routes import bp as auth_bp
from google_clients import calendar_client, sheets_client
from routes.anagrafiche import bp as anagrafiche_bp
from routes.cashflow import bp as cashflow_bp
from routes.movimenti import bp as movimenti_bp
from routes.queue import bp as queue_bp
from routes.report import bp as report_bp

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def index():
    return render_template("index.html")


@main_bp.route("/test-connessione")
@login_required
def test_connection():
    sheet_error = None
    sheet_title = None
    sheet_tabs = []
    try:
        spreadsheet = sheets_client.get_spreadsheet()
        sheet_title = spreadsheet.title
        sheet_tabs = [ws.title for ws in spreadsheet.worksheets()]
    except Exception as exc:  # noqa: BLE001 - vogliamo mostrare qualunque errore in UI
        sheet_error = str(exc)

    calendar_error = None
    events = []
    try:
        events = calendar_client.list_upcoming_events(max_results=10)
    except Exception as exc:  # noqa: BLE001
        calendar_error = str(exc)

    return render_template(
        "test_connection.html",
        sheet_title=sheet_title,
        sheet_tabs=sheet_tabs,
        sheet_error=sheet_error,
        events=events,
        calendar_error=calendar_error,
    )


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.IS_PRODUCTION,
    )
    CSRFProtect(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(anagrafiche_bp)
    app.register_blueprint(movimenti_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(cashflow_bp)

    @app.cli.command("init-sheet")
    def init_sheet():
        """Crea i tab mancanti nel Google Sheet configurato (idempotente)."""
        changed = sheets_client.ensure_workbook_structure()
        if changed:
            print(f"Tab creati o aggiornati: {', '.join(changed)}")
        else:
            print("Tutti i tab erano già presenti e aggiornati, nessuna modifica.")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
