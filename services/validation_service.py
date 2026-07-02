from datetime import datetime

import config
from google_clients import sheets_client
from services import anagrafica_service


def _to_float(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if value in (None, ""):
        return 0.0
    return float(str(value).replace(",", "."))


def corrisponde(valore_scope, target: str) -> bool:
    """Vero se una riga con questo valore di scope (Piattaforma o Tipo
    prestazione) si applica a `target`: vuoto/'Tutte' si applica a tutti,
    altrimenti serve corrispondenza esatta (case-insensitive). Stessa regola
    usata sia per le voci di costo variabili (Anagrafica_Costi) sia per i
    costi fissi (Costi_Fissi), così uno "Studio" scritto in un posto si
    comporta allo stesso modo ovunque.
    """
    valore_scope = str(valore_scope).strip().lower()
    return valore_scope in ("", "tutte") or valore_scope == target.strip().lower()


def get_costi_applicabili(piattaforma: str, tipo_prestazione: str) -> list[dict]:
    """Righe di Anagrafica_Costi che si applicano a questa piattaforma/tipo
    prestazione. Ogni riga rappresenta una voce di costo separata (fee
    piattaforma, tasse, Enpap, ...) e si sommano tutte tra loro. Una riga si
    applica se Piattaforma e/o Tipo prestazione sono vuoti/'Tutte' oppure
    corrispondono esattamente.
    """
    return [
        r
        for r in anagrafica_service.list_costi()
        if corrisponde(r.get("Piattaforma", ""), piattaforma)
        and corrisponde(r.get("Tipo prestazione", ""), tipo_prestazione)
    ]


def calcola_netto(prezzo_lordo: float, righe_costo: list[dict]) -> tuple[float, float]:
    """Somma tutte le voci di costo applicabili e restituisce (costo_totale, netto)."""
    totale_costo = 0.0
    for r in righe_costo:
        tipo_costo = str(r.get("Tipo costo", "")).strip().lower()
        valore = _to_float(r.get("Valore"))
        if tipo_costo.startswith("perc"):
            totale_costo += prezzo_lordo * valore / 100
        else:
            totale_costo += valore
    totale_costo = round(totale_costo, 2)
    return totale_costo, round(prezzo_lordo - totale_costo, 2)


def costi_breakdown(piattaforma: str, tipo_prestazione: str, prezzo_lordo: float) -> dict:
    """Scompone il costo totale nelle singole voci (Tasse, Enpap, ...) applicate
    a piattaforma/tipo prestazione, per mostrarle come colonne separate.
    Nota: usa il tariffario ATTUALE, quindi su un movimento vecchio può differire
    dal costo totale già salvato se il tariffario è cambiato nel frattempo.
    """
    righe_costo = get_costi_applicabili(piattaforma, tipo_prestazione)
    breakdown: dict[str, float] = {}
    for r in righe_costo:
        voce = str(r.get("Voce di costo", "")).strip() or "(senza voce)"
        tipo_costo = str(r.get("Tipo costo", "")).strip().lower()
        valore = _to_float(r.get("Valore"))
        importo = prezzo_lordo * valore / 100 if tipo_costo.startswith("perc") else valore
        breakdown[voce] = round(breakdown.get(voce, 0.0) + importo, 2)
    return breakdown


def valida_evento(
    event_id: str,
    event_date: str,
    paziente: str,
    piattaforma: str,
    tipo_prestazione: str,
    prezzo_lordo: float,
    note: str = "",
) -> None:
    """Calcola il netto e scrive la riga su Movimenti, poi marca l'evento come validato."""
    righe_costo = get_costi_applicabili(piattaforma, tipo_prestazione)
    costo_calcolato, netto = calcola_netto(prezzo_lordo, righe_costo)

    sheets_client.append_row(
        config.TAB_MOVIMENTI,
        [
            event_date,
            paziente,
            piattaforma,
            tipo_prestazione,
            prezzo_lordo,
            costo_calcolato,
            netto,
            "Da incassare",
            "",
            note,
        ],
    )
    sheets_client.append_row(
        config.TAB_EVENTI_PROCESSATI,
        [event_id, datetime.now().isoformat(timespec="seconds"), "validato"],
    )


def modifica_movimento(
    row: int,
    event_date: str,
    paziente: str,
    piattaforma: str,
    tipo_prestazione: str,
    prezzo_lordo: float,
    stato_pagamento: str,
    metodo_pagamento: str,
    note: str = "",
) -> None:
    """Sovrascrive una riga già validata su Movimenti, ricalcolando il netto
    (utile per correggere un errore senza dover annullare e rivalidare)."""
    righe_costo = get_costi_applicabili(piattaforma, tipo_prestazione)
    costo_calcolato, netto = calcola_netto(prezzo_lordo, righe_costo)

    sheets_client.update_row(
        config.TAB_MOVIMENTI,
        row,
        [
            event_date,
            paziente,
            piattaforma,
            tipo_prestazione,
            prezzo_lordo,
            costo_calcolato,
            netto,
            stato_pagamento,
            metodo_pagamento,
            note,
        ],
    )


def elimina_movimento(row: int) -> None:
    sheets_client.delete_row(config.TAB_MOVIMENTI, row)
