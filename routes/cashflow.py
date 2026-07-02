from datetime import date, datetime

from flask import Blueprint, render_template, request

from auth import login_required
from services import report_service, validation_service

bp = Blueprint("cashflow", __name__)


def _parse_date_arg(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@bp.route("/flusso-cassa")
@login_required
def index():
    oggi = date.today()
    primo_del_mese = oggi.replace(day=1)

    date_from = _parse_date_arg(request.args.get("da")) or primo_del_mese
    date_to = _parse_date_arg(request.args.get("a")) or oggi

    movimenti = report_service.list_movimenti(date_from, date_to)
    incassati = [m for m in movimenti if m["stato_pagamento"].strip().lower() == "incassato"]
    da_incassare = [m for m in movimenti if m["stato_pagamento"].strip().lower() != "incassato"]

    lordo_incassato = sum(m["lordo"] for m in incassati)
    netto_incassato = sum(m["netto"] for m in incassati)
    trattenute_incassate = sum(m["costo"] for m in incassati)

    trattenute_breakdown: dict[str, float] = {}
    for m in incassati:
        breakdown = validation_service.costi_breakdown(m["piattaforma"], m["tipo_prestazione"], m["lordo"])
        for voce, importo in breakdown.items():
            trattenute_breakdown[voce] = round(trattenute_breakdown.get(voce, 0.0) + importo, 2)

    lordo_da_incassare = sum(m["lordo"] for m in da_incassare)
    netto_da_incassare = sum(m["netto"] for m in da_incassare)

    costi_fissi = report_service.costi_fissi_nel_periodo(date_from, date_to)
    totale_costi_fissi = sum(c["importo_periodo"] for c in costi_fissi)

    cassa_disponibile = netto_incassato - totale_costi_fissi

    return render_template(
        "cashflow.html",
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        lordo_incassato=lordo_incassato,
        netto_incassato=netto_incassato,
        trattenute_incassate=trattenute_incassate,
        trattenute_breakdown=trattenute_breakdown,
        incassati=incassati,
        lordo_da_incassare=lordo_da_incassare,
        netto_da_incassare=netto_da_incassare,
        costi_fissi=costi_fissi,
        totale_costi_fissi=totale_costi_fissi,
        cassa_disponibile=cassa_disponibile,
        numero_incassati=len(incassati),
        numero_da_incassare=len(da_incassare),
    )
