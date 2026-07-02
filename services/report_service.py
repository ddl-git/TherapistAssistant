from datetime import date, datetime

import config
from google_clients import sheets_client
from services import anagrafica_service, validation_service

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

    Nota: il Netto qui è il margine di contribuzione (lordo - costi variabili
    per seduta), non include i costi fissi — quelli si vedono solo nel Flusso
    di cassa, come spesa di periodo, non spalmati sulla singola seduta (vedi
    discussione: spalmarli qui renderebbe il Netto instabile, perché
    cambierebbe ogni volta che si aggiunge una seduta nello stesso mese).
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


def _importo_costo_fisso_nel_periodo(riga: dict, date_from: date, date_to: date) -> dict | None:
    """Ripartisce a giorni UNA riga di costo fisso sul periodo [date_from, date_to].

    Converte l'importo mensile in un tasso giornaliero (importo_mensile * 12 /
    365.25) e lo moltiplica per i giorni di sovrapposizione tra la durata del
    costo (data inizio / data fine) e il periodo richiesto. Un costo senza
    data fine è considerato ancora attivo oggi. None se non si applica al periodo.
    """
    inizio = _parse_date(riga.get("Data inizio"))
    if not inizio:
        return None
    fine = _parse_date(riga.get("Data fine"))

    overlap_da = max(inizio, date_from)
    overlap_a = min(fine, date_to) if fine else date_to
    giorni = (overlap_a - overlap_da).days + 1
    if giorni <= 0:
        return None

    importo_mensile = _parse_float(riga.get("Importo mensile"))
    tasso_giornaliero = importo_mensile * 12 / 365.25
    return {"giorni": giorni, "importo_periodo": round(tasso_giornaliero * giorni, 2)}


def costi_fissi_nel_periodo(date_from: date, date_to: date) -> list[dict]:
    """Elenca tutti i costi fissi attivi nel periodo [date_from, date_to] con
    il relativo importo prorata a giorni (vedi `_importo_costo_fisso_nel_periodo`),
    indipendentemente dal loro scope Piattaforma/Tipo prestazione: usato per il
    totale di cassa reale nel Flusso di cassa, che deve contare ogni costo per
    intero sul periodo.
    """
    risultato = []
    for r in anagrafica_service.list_costi_fissi():
        dettaglio = _importo_costo_fisso_nel_periodo(r, date_from, date_to)
        if not dettaglio:
            continue
        risultato.append(
            {
                "nome": r.get("Nome", ""),
                "piattaforma": r.get("Piattaforma", ""),
                "tipo_prestazione": r.get("Tipo prestazione", ""),
                "importo_mensile": _parse_float(r.get("Importo mensile")),
                "giorni": dettaglio["giorni"],
                "importo_periodo": dettaglio["importo_periodo"],
            }
        )
    return risultato
