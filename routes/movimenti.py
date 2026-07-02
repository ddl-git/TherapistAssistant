from flask import Blueprint, redirect, render_template, request, url_for

from auth import login_required
from services import anagrafica_service, report_service, validation_service

bp = Blueprint("movimenti", __name__)


@bp.route("/movimenti")
@login_required
def list_movimenti():
    movimenti = sorted(
        report_service.list_movimenti(),
        key=lambda m: m["data"] or "",
        reverse=True,
    )

    voci_colonne = []
    for m in movimenti:
        breakdown = validation_service.costi_breakdown(m["piattaforma"], m["tipo_prestazione"], m["lordo"])
        m["costi_breakdown"] = breakdown
        for voce in breakdown:
            if voce not in voci_colonne:
                voci_colonne.append(voce)

    incassati = [m for m in movimenti if m["stato_pagamento"].strip().lower() == "incassato"]
    da_incassare = [m for m in movimenti if m["stato_pagamento"].strip().lower() != "incassato"]

    riepilogo = {
        "netto_totale": sum(m["netto"] for m in movimenti),
        "incassato": sum(m["netto"] for m in incassati),
        "da_incassare": sum(m["netto"] for m in da_incassare),
        "trattenute": sum(m["costo"] for m in movimenti),
        "conteggio_tutti": len(movimenti),
        "conteggio_incassati": len(incassati),
        "conteggio_da_incassare": len(da_incassare),
    }

    return render_template(
        "movimenti.html", movimenti=movimenti, voci_colonne=voci_colonne, riepilogo=riepilogo
    )


@bp.route("/movimenti/<int:row>/pagamento", methods=["POST"])
@login_required
def aggiorna_pagamento(row):
    stato = request.form.get("stato_pagamento", "Da incassare")
    metodo = request.form.get("metodo_pagamento", "").strip()
    report_service.update_pagamento(row, stato, metodo)
    return redirect(url_for("movimenti.list_movimenti"))


@bp.route("/movimenti/<int:row>/modifica", methods=["GET", "POST"])
@login_required
def modifica_movimento(row):
    if request.method == "POST":
        combo = request.form.get("combo", "")
        piattaforma, _, tipo_prestazione = combo.partition("::")
        prezzo_lordo = float((request.form.get("prezzo_lordo") or "0").replace(",", "."))
        validation_service.modifica_movimento(
            row=row,
            event_date=request.form.get("data", ""),
            paziente=request.form.get("paziente", "").strip(),
            piattaforma=piattaforma,
            tipo_prestazione=tipo_prestazione,
            prezzo_lordo=prezzo_lordo,
            stato_pagamento=request.form.get("stato_pagamento", "Da incassare"),
            metodo_pagamento=request.form.get("metodo_pagamento", "").strip(),
            note=request.form.get("note", "").strip(),
        )
        return redirect(url_for("movimenti.list_movimenti"))

    movimento = next((m for m in report_service.list_movimenti() if m["_row"] == row), None)
    if movimento is None:
        return redirect(url_for("movimenti.list_movimenti"))

    ricavi = anagrafica_service.list_ricavi()
    combos = [
        {
            "value": f"{r['Piattaforma']}::{r['Tipo prestazione']}",
            "label": f"{r['Piattaforma']} — {r['Tipo prestazione']} ({r['Prezzo lordo']} €)",
            "prezzo": r["Prezzo lordo"],
        }
        for r in ricavi
    ]
    combo_attuale = f"{movimento['piattaforma']}::{movimento['tipo_prestazione']}"

    return render_template(
        "modifica_movimento.html",
        m=movimento,
        combos=combos,
        combo_attuale=combo_attuale,
    )


@bp.route("/movimenti/<int:row>/elimina", methods=["POST"])
@login_required
def elimina_movimento(row):
    validation_service.elimina_movimento(row)
    return redirect(url_for("movimenti.list_movimenti"))
