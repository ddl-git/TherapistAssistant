from datetime import date, datetime

import config
from google_clients import sheets_client
from services import anagrafica_service, validation_service

INCASSATO = "Incassato"
DA_INCASSARE = "Da incassare"


def _parse_float(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return 0.0


def _parse_date(value):
    if not value:
        return None
    text = str(value)[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def list_movimenti(date_from: date = None, date_to: date = None) -> list[dict]:
    """Legge i movimenti dal foglio, ma ricalcola SEMPRE costo e netto dal
    tariffario attuale (lordo + Anagrafica_Costi di oggi), invece di fidarsi
    dei valori scritti nel foglio al momento della validazione. Così il netto
    mostrato è sempre coerente con il tariffario in vigore quando si apre la
    pagina, anche se nel frattempo è cambiato.
    """
    rows = sheets_client.get_records_with_rows(config.TAB_MOVIMENTI)
    result = []
    for r in rows:
        data = _parse_date(r.get("Data"))
        if date_from and data and data < date_from:
            continue
        if date_to and data and data > date_to:
            continue

        piattaforma = r.get("Piattaforma", "")
        tipo_prestazione = r.get("Tipo prestazione", "")
        lordo = _parse_float(r.get("Importo lordo"))
        righe_costo = validation_service.get_costi_applicabili(piattaforma, tipo_prestazione)
        costo, netto = validation_service.calcola_netto(lordo, righe_costo)

        result.append(
            {
                "_row": r["_row"],
                "data": data,
                "paziente": r.get("Paziente", ""),
                "piattaforma": piattaforma,
                "tipo_prestazione": tipo_prestazione,
                "lordo": lordo,
                "costo": costo,
                "netto": netto,
                "stato_pagamento": r.get("Stato pagamento", "") or DA_INCASSARE,
                "metodo_pagamento": r.get("Metodo pagamento", ""),
                "note": r.get("Note", ""),
            }
        )
    return result


def update_pagamento(row: int, stato_pagamento: str, metodo_pagamento: str) -> None:
    sheets_client.update_cell_by_header(config.TAB_MOVIMENTI, row, "Stato pagamento", stato_pagamento)
    sheets_client.update_cell_by_header(config.TAB_MOVIMENTI, row, "Metodo pagamento", metodo_pagamento)


def monthly_totals(movimenti: list[dict]) -> dict:
    """Totali per mese (YYYY-MM): dovuto vs incassato, lordo e netto."""
    totals = {}
    for m in movimenti:
        if not m["data"]:
            continue
        key = m["data"].strftime("%Y-%m")
        t = totals.setdefault(
            key,
            {"lordo_dovuto": 0.0, "lordo_incassato": 0.0, "netto_dovuto": 0.0, "netto_incassato": 0.0},
        )
        t["lordo_dovuto"] += m["lordo"]
        t["netto_dovuto"] += m["netto"]
        if m["stato_pagamento"].strip().lower() == INCASSATO.lower():
            t["lordo_incassato"] += m["lordo"]
            t["netto_incassato"] += m["netto"]
    return dict(sorted(totals.items()))


def costi_fissi_nel_periodo(date_from: date, date_to: date) -> list[dict]:
    """Ripartisce a giorni i costi fissi attivi nel periodo [date_from, date_to].

    Ogni costo fisso ha un importo mensile; lo converto in un tasso giornaliero
    (importo_mensile * 12 / 365.25) e lo moltiplico per i giorni di
    sovrapposizione tra la sua durata (data inizio / data fine) e il periodo
    richiesto. Un costo senza data fine è considerato ancora attivo oggi.
    """
    risultato = []
    for r in anagrafica_service.list_costi_fissi():
        inizio = _parse_date(r.get("Data inizio"))
        if not inizio:
            continue
        fine = _parse_date(r.get("Data fine"))

        overlap_da = max(inizio, date_from)
        overlap_a = min(fine, date_to) if fine else date_to
        giorni = (overlap_a - overlap_da).days + 1
        if giorni <= 0:
            continue

        importo_mensile = _parse_float(r.get("Importo mensile"))
        tasso_giornaliero = importo_mensile * 12 / 365.25
        importo_periodo = round(tasso_giornaliero * giorni, 2)

        risultato.append(
            {
                "nome": r.get("Nome", ""),
                "importo_mensile": importo_mensile,
                "giorni": giorni,
                "importo_periodo": importo_periodo,
            }
        )
    return risultato


def breakdown_by(movimenti: list[dict], field: str) -> dict:
    """Totali lordo/netto raggruppati per un campo (tipo_prestazione, paziente, piattaforma)."""
    totals = {}
    for m in movimenti:
        key = m.get(field) or "(non specificato)"
        t = totals.setdefault(key, {"lordo": 0.0, "netto": 0.0, "conteggio": 0})
        t["lordo"] += m["lordo"]
        t["netto"] += m["netto"]
        t["conteggio"] += 1
    return dict(sorted(totals.items(), key=lambda kv: -kv[1]["lordo"]))
