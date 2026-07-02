import csv
import io
from datetime import datetime

from flask import Blueprint, Response, render_template, request, send_file

from auth import login_required
from services import report_service


def _serialize_movimenti(movimenti):
    """Righe pronte per essere incorporate come JSON nella pagina Report: il
    filtro per Paziente/Piattaforma/Tipo prestazione/Stato pagamento e il
    ricalcolo di card/grafico/breakdown avvengono lato client via JS, così
    l'utente può incrociare i filtri senza ricaricare la pagina.
    """
    return [
        {
            "data": m["data"].isoformat() if m["data"] else None,
            "paziente": m["paziente"],
            "piattaforma": m["piattaforma"],
            "tipo_prestazione": m["tipo_prestazione"],
            "lordo": m["lordo"],
            "costo": m["costo"],
            "netto": m["netto"],
            "stato_pagamento": m["stato_pagamento"],
            "metodo_pagamento": m["metodo_pagamento"],
            "note": m["note"],
        }
        for m in movimenti
    ]


def _opzioni_filtro(movimenti, campo):
    return sorted({m[campo] for m in movimenti if m[campo]})

bp = Blueprint("report", __name__)


def _parse_date_arg(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _filtered_movimenti():
    date_from = _parse_date_arg(request.args.get("da"))
    date_to = _parse_date_arg(request.args.get("a"))
    return report_service.list_movimenti(date_from, date_to)


@bp.route("/report")
@login_required
def index():
    movimenti = _filtered_movimenti()

    return render_template(
        "report.html",
        movimenti_json=_serialize_movimenti(movimenti),
        opzioni_pazienti=_opzioni_filtro(movimenti, "paziente"),
        opzioni_piattaforme=_opzioni_filtro(movimenti, "piattaforma"),
        opzioni_tipi=_opzioni_filtro(movimenti, "tipo_prestazione"),
        date_from=request.args.get("da", ""),
        date_to=request.args.get("a", ""),
    )


@bp.route("/report/export.csv")
@login_required
def export_csv():
    movimenti = _filtered_movimenti()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Data", "Paziente", "Piattaforma", "Tipo prestazione",
            "Lordo", "Costo", "Netto", "Stato pagamento", "Metodo pagamento", "Note",
        ]
    )
    for m in movimenti:
        writer.writerow(
            [
                m["data"] or "", m["paziente"], m["piattaforma"], m["tipo_prestazione"],
                m["lordo"], m["costo"], m["netto"], m["stato_pagamento"], m["metodo_pagamento"], m["note"],
            ]
        )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=movimenti.csv"},
    )


@bp.route("/report/export.xlsx")
@login_required
def export_excel():
    from openpyxl import Workbook

    movimenti = _filtered_movimenti()
    wb = Workbook()
    ws = wb.active
    ws.title = "Movimenti"
    ws.append(
        [
            "Data", "Paziente", "Piattaforma", "Tipo prestazione",
            "Lordo", "Costo", "Netto", "Stato pagamento", "Metodo pagamento", "Note",
        ]
    )
    for m in movimenti:
        ws.append(
            [
                str(m["data"]) if m["data"] else "", m["paziente"], m["piattaforma"], m["tipo_prestazione"],
                m["lordo"], m["costo"], m["netto"], m["stato_pagamento"], m["metodo_pagamento"], m["note"],
            ]
        )

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="movimenti.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
