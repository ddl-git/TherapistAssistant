import csv
import io
from datetime import datetime

from flask import Blueprint, Response, render_template, request, send_file

from auth import login_required
from services import report_service

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

    totale_lordo = sum(m["lordo"] for m in movimenti)
    totale_netto = sum(m["netto"] for m in movimenti)
    incassati = [m for m in movimenti if m["stato_pagamento"].strip().lower() == "incassato"]
    totale_incassato_lordo = sum(m["lordo"] for m in incassati)
    totale_incassato_netto = sum(m["netto"] for m in incassati)

    return render_template(
        "report.html",
        monthly=report_service.monthly_totals(movimenti),
        per_prestazione=report_service.breakdown_by(movimenti, "tipo_prestazione"),
        per_paziente=report_service.breakdown_by(movimenti, "paziente"),
        per_piattaforma=report_service.breakdown_by(movimenti, "piattaforma"),
        totale_lordo=totale_lordo,
        totale_netto=totale_netto,
        totale_incassato_lordo=totale_incassato_lordo,
        totale_incassato_netto=totale_incassato_netto,
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
