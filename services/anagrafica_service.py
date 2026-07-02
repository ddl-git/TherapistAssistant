import config
from google_clients import sheets_client


def list_ricavi() -> list[dict]:
    """Righe di Anagrafica_Ricavi, con '_row' per poterle modificare/eliminare."""
    return sheets_client.get_records_with_rows(config.TAB_ANAGRAFICA_RICAVI)


def add_ricavo(piattaforma: str, tipo_prestazione: str, prezzo_lordo) -> None:
    sheets_client.append_row(
        config.TAB_ANAGRAFICA_RICAVI, [piattaforma, tipo_prestazione, prezzo_lordo]
    )


def update_ricavo(row: int, piattaforma: str, tipo_prestazione: str, prezzo_lordo) -> None:
    sheets_client.update_row(
        config.TAB_ANAGRAFICA_RICAVI, row, [piattaforma, tipo_prestazione, prezzo_lordo]
    )


def delete_ricavo(row: int) -> None:
    sheets_client.delete_row(config.TAB_ANAGRAFICA_RICAVI, row)


def list_costi() -> list[dict]:
    return sheets_client.get_records_with_rows(config.TAB_ANAGRAFICA_COSTI)


def add_costo(piattaforma: str, tipo_prestazione: str, voce_costo: str, tipo_costo: str, valore) -> None:
    sheets_client.append_row(
        config.TAB_ANAGRAFICA_COSTI, [piattaforma, tipo_prestazione, voce_costo, tipo_costo, valore]
    )


def update_costo(row: int, piattaforma: str, tipo_prestazione: str, voce_costo: str, tipo_costo: str, valore) -> None:
    sheets_client.update_row(
        config.TAB_ANAGRAFICA_COSTI, row, [piattaforma, tipo_prestazione, voce_costo, tipo_costo, valore]
    )


def delete_costo(row: int) -> None:
    sheets_client.delete_row(config.TAB_ANAGRAFICA_COSTI, row)


def list_piattaforme() -> list[dict]:
    return sheets_client.get_records_with_rows(config.TAB_PIATTAFORME)


def add_piattaforma(nome: str) -> None:
    sheets_client.append_row(config.TAB_PIATTAFORME, [nome])


def delete_piattaforma(row: int) -> None:
    sheets_client.delete_row(config.TAB_PIATTAFORME, row)


def list_tipi_prestazione() -> list[dict]:
    return sheets_client.get_records_with_rows(config.TAB_TIPI_PRESTAZIONE)


def add_tipo_prestazione(nome: str) -> None:
    sheets_client.append_row(config.TAB_TIPI_PRESTAZIONE, [nome])


def delete_tipo_prestazione(row: int) -> None:
    sheets_client.delete_row(config.TAB_TIPI_PRESTAZIONE, row)


def seed_piattaforme_e_tipi_da_tariffario() -> None:
    """Se le anagrafiche centralizzate Piattaforme/Tipi_Prestazione sono ancora
    vuote, le popola con i valori già distinti presenti in Anagrafica_Ricavi e
    Anagrafica_Costi, per non perdere i dati inseriti prima che esistessero
    questi menu a tendina. Idempotente: non fa nulla se già popolate.
    """
    if not list_piattaforme():
        nomi = set()
        for r in list_ricavi() + list_costi():
            valore = str(r.get("Piattaforma", "")).strip()
            if valore:
                nomi.add(valore)
        for nome in sorted(nomi):
            add_piattaforma(nome)

    if not list_tipi_prestazione():
        nomi = set()
        for r in list_ricavi():
            valore = str(r.get("Tipo prestazione", "")).strip()
            if valore:
                nomi.add(valore)
        for r in list_costi():
            valore = str(r.get("Tipo prestazione", "")).strip()
            if valore and valore.lower() != "tutte":
                nomi.add(valore)
        for nome in sorted(nomi):
            add_tipo_prestazione(nome)


def list_voci_costo() -> list[dict]:
    return sheets_client.get_records_with_rows(config.TAB_VOCI_COSTO)


def add_voce_costo(nome: str) -> None:
    sheets_client.append_row(config.TAB_VOCI_COSTO, [nome])


def delete_voce_costo(row: int) -> None:
    sheets_client.delete_row(config.TAB_VOCI_COSTO, row)


def seed_voci_costo_default() -> None:
    """Se l'anagrafica Voci_Costo è ancora vuota, la popola con le voci più
    comuni (fee piattaforma, tasse, contributi ENPAP), sempre modificabili."""
    if not list_voci_costo():
        for nome in ("Fee piattaforma", "Tasse", "Enpap"):
            add_voce_costo(nome)


def list_costi_fissi() -> list[dict]:
    return sheets_client.get_records_with_rows(config.TAB_COSTI_FISSI)


def add_costo_fisso(nome: str, importo_mensile, data_inizio: str, data_fine: str = "") -> None:
    sheets_client.append_row(config.TAB_COSTI_FISSI, [nome, importo_mensile, data_inizio, data_fine])


def update_costo_fisso(row: int, nome: str, importo_mensile, data_inizio: str, data_fine: str = "") -> None:
    sheets_client.update_row(config.TAB_COSTI_FISSI, row, [nome, importo_mensile, data_inizio, data_fine])


def delete_costo_fisso(row: int) -> None:
    sheets_client.delete_row(config.TAB_COSTI_FISSI, row)


def list_pazienti() -> list[dict]:
    return sheets_client.get_records_with_rows(config.TAB_PAZIENTI)


def add_paziente(nome: str, contatto: str) -> None:
    sheets_client.append_row(config.TAB_PAZIENTI, [nome, contatto])


def update_paziente(row: int, nome: str, contatto: str) -> None:
    sheets_client.update_row(config.TAB_PAZIENTI, row, [nome, contatto])


def find_paziente_by_nome(nome: str) -> dict | None:
    """Cerca un paziente per nome, confronto case-insensitive e senza spazi
    superflui. Usato per capire se un nome proposto dalla coda è già noto."""
    nome_normalizzato = nome.strip().lower()
    if not nome_normalizzato:
        return None
    for r in list_pazienti():
        if str(r.get("Nome", "")).strip().lower() == nome_normalizzato:
            return r
    return None


def keyword_whitelist() -> set[str]:
    """Parole chiave (piattaforme e tipi prestazione) note dal tariffario,
    usate per riconoscere quali eventi calendario sono appuntamenti pazienti.
    """
    keywords = set()
    for row in list_ricavi():
        piattaforma = str(row.get("Piattaforma", "")).strip()
        tipo = str(row.get("Tipo prestazione", "")).strip()
        if piattaforma:
            keywords.add(piattaforma.lower())
        if tipo:
            keywords.add(tipo.lower())
    return keywords
