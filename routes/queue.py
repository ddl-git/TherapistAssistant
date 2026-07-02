from flask import Blueprint, redirect, render_template, request, url_for

from auth import login_required
from services import anagrafica_service, sync_service, validation_service

bp = Blueprint("queue", __name__)


@bp.route("/coda")
@login_required
def list_queue():
    events = sync_service.list_queue_events()
    return render_template("queue.html", events=events)


@bp.route("/coda/ignora/<event_id>", methods=["POST"])
@login_required
def ignore_event(event_id):
    sync_service.mark_event_ignored(event_id)
    return redirect(url_for("queue.list_queue"))


@bp.route("/coda/valida/<event_id>", methods=["GET", "POST"])
@login_required
def validate_event(event_id):
    title = request.values.get("title", "")
    start = request.values.get("start", "")
    event_date = start.split("T")[0] if start else ""

    if request.method == "POST":
        combo = request.form.get("combo", "")
        piattaforma, _, tipo_prestazione = combo.partition("::")
        prezzo_lordo = float((request.form.get("prezzo_lordo") or "0").replace(",", "."))
        paziente = request.form.get("paziente", "").strip()

        if paziente and request.form.get("aggiungi_paziente") == "on":
            if not anagrafica_service.find_paziente_by_nome(paziente):
                anagrafica_service.add_paziente(paziente, "")

        validation_service.valida_evento(
            event_id=event_id,
            event_date=request.form.get("event_date", event_date),
            paziente=paziente,
            piattaforma=piattaforma,
            tipo_prestazione=tipo_prestazione,
            prezzo_lordo=prezzo_lordo,
            note=request.form.get("note", "").strip(),
        )
        return redirect(url_for("queue.list_queue"))

    ricavi = anagrafica_service.list_ricavi()
    combos = [
        {
            "value": f"{r['Piattaforma']}::{r['Tipo prestazione']}",
            "label": f"{r['Piattaforma']} — {r['Tipo prestazione']} ({r['Prezzo lordo']} €)",
            "prezzo": r["Prezzo lordo"],
        }
        for r in ricavi
    ]
    guessed_paziente = sync_service.guess_patient_name(title, anagrafica_service.keyword_whitelist())
    matched_combo = sync_service.find_matching_combo(title, combos)
    paziente_esistente = anagrafica_service.find_paziente_by_nome(guessed_paziente)

    return render_template(
        "validate.html",
        event_id=event_id,
        title=title,
        event_date=event_date,
        guessed_paziente=guessed_paziente,
        combos=combos,
        matched_combo=matched_combo,
        paziente_esistente=paziente_esistente,
        pazienti=anagrafica_service.list_pazienti(),
    )
