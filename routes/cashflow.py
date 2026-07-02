import csv
import io
from datetime import date, datetime

from flask import Blueprint, Response, render_template, request

import config
from auth import login_required
from services import report_service

bp = Blueprint("cashflow", __name__)


def _parse_date_arg(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _stato_movimento(m, oggi):
    if m["stato_pagamento"].strip().lower() == "incassato":
        return "incassato"
    if m["data"] and (oggi - m["data"]).days > config.GIORNI_SCADUTO:
        return "scaduto"
    return "da_incassare"


def _movimenti_del_periodo(date_from, date_to):
    """Movimenti del periodo, con lo stato derivato (incassato/da_incassare/
    scaduto) e prima di applicare i filtri Stato/Metodo/Paziente della pagina.
    """
    oggi = date.today()
    movimenti = report_service.list_movimenti(date_from, date_to)
    for m in movimenti:
        m["stato_derivato"] = _stato_movimento(m, oggi)
    return movimenti


def _applica_filtri(movimenti, stato, metodo, paziente):
    result = movimenti
    if stato:
        result = [m for m in result if m["stato_derivato"] == stato]
    if metodo:
        result = [m for m in result if m["metodo_pagamento"] == metodo]
    if paziente:
        query = paziente.strip().lower()
        result = [m for m in result if query in m["paziente"].lower()]
    return result


def _contesto(date_from, date_to, stato, metodo, paziente):
    movimenti_periodo = _movimenti_del_periodo(date_from, date_to)
    opzioni_metodo = sorted({m["metodo_pagamento"] for m in movimenti_periodo if m["metodo_pagamento"]})

    movimenti = _applica_filtri(movimenti_periodo, stato, metodo, paziente)
    incassati = [m for m in movimenti if m["stato_derivato"] == "incassato"]
    da_incassare = [m for m in movimenti if m["stato_derivato"] != "incassato"]

    lordo_incassato = sum(m["lordo"] for m in incassati)
    fee_incassate = sum(m["costo"] for m in incassati)
    netto_operativo = round(lordo_incassato - fee_incassate, 2)

    costi_variabili_per_piattaforma: dict[str, float] = {}
    for m in incassati:
        chiave = m["piattaforma"] or "(non specificato)"
        costi_variabili_per_piattaforma[chiave] = round(
            costi_variabili_per_piattaforma.get(chiave, 0.0) + m["costo"], 2
        )

    costi_fissi = report_service.costi_fissi_nel_periodo(date_from, date_to)
    totale_costi_fissi = sum(c["importo_periodo"] for c in costi_fissi)

    accantonamento = round(config.ALIQUOTA_ACCANTONAMENTO * netto_operativo, 2)
    imposte_forfettario_stimate = round(config.ALIQUOTA_FORFETTARIO * netto_operativo, 2)
    disponibile_reale = round(netto_operativo - totale_costi_fissi - accantonamento, 2)

    lordo_da_incassare = sum(m["lordo"] for m in da_incassare)
    netto_da_incassare = sum(m["netto"] for m in da_incassare)

    ledger = [
        {
            "tipo": "Entrata",
            "data": m["data"],
            "soggetto": m["paziente"],
            "descrizione": f"{m['tipo_prestazione']} · {m['piattaforma']}",
            "stato": m["stato_pagamento"],
            "lordo": m["lordo"],
            "netto": m["netto"],
            "filtro": m["stato_derivato"],
        }
        for m in movimenti
    ]
    ledger.sort(key=lambda r: r["data"] or date.min, reverse=True)
    for piattaforma, totale in costi_variabili_per_piattaforma.items():
        ledger.append(
            {
                "tipo": "Costo",
                "data": date_to,
                "soggetto": f"Commissioni {piattaforma}",
                "descrizione": "Costi variabili del periodo",
                "stato": "-",
                "lordo": None,
                "netto": -totale,
                "filtro": "costo",
            }
        )

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "stato": stato,
        "metodo": metodo,
        "paziente": paziente,
        "opzioni_metodo": opzioni_metodo,
        "lordo_incassato": lordo_incassato,
        "fee_incassate": fee_incassate,
        "netto_operativo": netto_operativo,
        "costi_variabili_per_piattaforma": costi_variabili_per_piattaforma,
        "totale_costi_variabili": fee_incassate,
        "costi_fissi": costi_fissi,
        "totale_costi_fissi": totale_costi_fissi,
        "accantonamento": accantonamento,
        "imposte_forfettario_stimate": imposte_forfettario_stimate,
        "disponibile_reale": disponibile_reale,
        "da_incassare": sorted(da_incassare, key=lambda m: m["data"] or date.min),
        "lordo_da_incassare": lordo_da_incassare,
        "netto_da_incassare": netto_da_incassare,
        "numero_da_incassare": len(da_incassare),
        "numero_incassati": len(incassati),
        "ledger": ledger,
    }


@bp.route("/flusso-cassa")
@login_required
def index():
    oggi = date.today()
    primo_del_mese = oggi.replace(day=1)

    date_from = _parse_date_arg(request.args.get("da")) or primo_del_mese
    date_to = _parse_date_arg(request.args.get("a")) or oggi
    stato = request.args.get("stato", "")
    metodo = request.args.get("metodo", "")
    paziente = request.args.get("paziente", "")

    ctx = _contesto(date_from, date_to, stato, metodo, paziente)
    return render_template(
        "cashflow.html",
        pagina_corrente=request.full_path,
        oggi=oggi.isoformat(),
        oggi_anno_inizio=oggi.replace(month=1, day=1).isoformat(),
        aliquota_accantonamento_pct=round(config.ALIQUOTA_ACCANTONAMENTO * 100),
        aliquota_forfettario_pct=round(config.ALIQUOTA_FORFETTARIO * 100),
        **ctx,
    )


@bp.route("/flusso-cassa/export.csv")
@login_required
def export_csv():
    oggi = date.today()
    primo_del_mese = oggi.replace(day=1)
    date_from = _parse_date_arg(request.args.get("da")) or primo_del_mese
    date_to = _parse_date_arg(request.args.get("a")) or oggi
    stato = request.args.get("stato", "")
    metodo = request.args.get("metodo", "")
    paziente = request.args.get("paziente", "")

    ctx = _contesto(date_from, date_to, stato, metodo, paziente)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Tipo", "Data", "Soggetto", "Descrizione", "Stato", "Lordo", "Netto"])
    for r in ctx["ledger"]:
        writer.writerow(
            [r["tipo"], r["data"].isoformat() if r["data"] else "", r["soggetto"], r["descrizione"], r["stato"],
             r["lordo"] if r["lordo"] is not None else "", r["netto"]]
        )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=flusso-cassa.csv"},
    )
