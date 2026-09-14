from calendar import monthrange
from datetime import date
from urllib.parse import urlparse

from flask import Blueprint, redirect, render_template, request, url_for

from auth import login_required
from services import anagrafica_service, report_service, validation_service

bp = Blueprint("movimenti", __name__)


def _next_sicuro(url_arg):
    """Redirect verso `next` solo se è un percorso locale (niente
    scheme/netloc): evita open redirect se il valore viene manomesso."""
    if not url_arg:
        return None
    parsed = urlparse(url_arg)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return None
    return url_arg


def _mese_richiesto(value):
    """Interpreta il parametro `mese` (YYYY-MM). None = tutti i mesi."""
    if not value:
        return None
    try:
        anno, mese = (int(p) for p in value.split("-", 1))
        return date(anno, mese, 1)
    except (TypeError, ValueError):
        return None


@bp.route("/movimenti")
@login_required
def list_movimenti():
    mese_param = request.args.get("mese", date.today().strftime("%Y-%m"))
    primo_del_mese = _mese_richiesto(mese_param)
    date_from = date_to = None
    if primo_del_mese:
        date_from = primo_del_mese
        date_to = primo_del_mese.replace(day=monthrange(primo_del_mese.year, primo_del_mese.month)[1])

    movimenti = sorted(
        report_service.list_movimenti(date_from, date_to),
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
        "movimenti.html",
        movimenti=movimenti,
        voci_colonne=voci_colonne,
        riepilogo=riepilogo,
        mese_selezionato=mese_param if primo_del_mese else "",
    )


@bp.route("/movimenti/<int:row>/pagamento", methods=["POST"])
@login_required
def aggiorna_pagamento(row):
    stato = request.form.get("stato_pagamento", "Da incassare")
    metodo = request.form.get("metodo_pagamento", "").strip()
    report_service.update_pagamento(row, stato, metodo)
    next_url = _next_sicuro(request.form.get("next"))
    return redirect(next_url or url_for("movimenti.list_movimenti"))


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
