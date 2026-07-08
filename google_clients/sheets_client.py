import time

import gspread
from google.oauth2.service_account import Credentials

import config
from google_clients import with_retry

_client = None
_spreadsheet = None

# Cache in memoria per ridurre le letture ripetute verso l'API di Google
# Sheets (che ha un limite di richieste al minuto): ogni tab letto resta
# valido per pochi secondi, ed è invalidato subito da qualunque scrittura.
_CACHE_TTL_SECONDS = 15
_cache: dict[str, tuple[float, list[dict]]] = {}


def _invalidate_cache(tab_name: str) -> None:
    _cache.pop(tab_name, None)


def _read_records_cached(tab_name: str) -> list[dict]:
    cached = _cache.get(tab_name)
    if cached is not None and (time.monotonic() - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]
    records = with_retry(lambda: get_worksheet(tab_name).get_all_records(numericise_ignore=["all"]))
    _cache[tab_name] = (time.monotonic(), records)
    return records


def get_client() -> gspread.Client:
    global _client
    if _client is None:
        creds = Credentials.from_service_account_info(
            config.load_service_account_info(), scopes=config.GOOGLE_API_SCOPES
        )
        _client = gspread.authorize(creds)
    return _client


def get_spreadsheet() -> gspread.Spreadsheet:
    global _spreadsheet
    if _spreadsheet is None:
        _spreadsheet = get_client().open_by_key(config.GOOGLE_SHEET_ID)
    return _spreadsheet


def get_worksheet(tab_name: str) -> gspread.Worksheet:
    return get_spreadsheet().worksheet(tab_name)


def ensure_workbook_structure() -> list[str]:
    """Crea i tab mancanti con le intestazioni corrette e aggiorna le intestazioni
    dei tab esistenti ma ancora vuoti (nessuna riga di dati sotto l'header).
    Idempotente. Non tocca mai un tab che contiene già dei dati.

    Restituisce la lista dei tab creati o aggiornati (vuota se non serviva nulla).
    """
    spreadsheet = get_spreadsheet()
    existing = {ws.title: ws for ws in spreadsheet.worksheets()}
    changed = []

    for tab_name, headers in config.SHEET_STRUCTURE.items():
        if tab_name not in existing:
            worksheet = spreadsheet.add_worksheet(
                title=tab_name, rows=100, cols=max(len(headers), 1)
            )
            worksheet.append_row(headers)
            changed.append(tab_name)
            continue

        worksheet = existing[tab_name]
        all_values = worksheet.get_all_values()
        current_headers = all_values[0] if all_values else []
        has_data_rows = len(all_values) > 1
        if current_headers != headers and not has_data_rows:
            worksheet.resize(rows=max(worksheet.row_count, 100), cols=max(len(headers), 1))
            worksheet.update("A1", [headers])
            changed.append(tab_name)

    return changed


def get_all_records(tab_name: str) -> list[dict]:
    """Legge tutte le righe di un tab come lista di dict (chiave = colonna header)."""
    return _read_records_cached(tab_name)


def get_records_with_rows(tab_name: str) -> list[dict]:
    """Come get_all_records, ma ogni dict include anche '_row': il numero di riga
    reale nel foglio (utile per poi modificare o eliminare quella riga precisa).
    """
    records = _read_records_cached(tab_name)
    return [dict(record, _row=i + 2) for i, record in enumerate(records)]


def append_row(tab_name: str, row_values: list) -> None:
    with_retry(lambda: get_worksheet(tab_name).append_row(row_values))
    _invalidate_cache(tab_name)


def update_row(tab_name: str, row_number: int, row_values: list) -> None:
    with_retry(lambda: get_worksheet(tab_name).update(f"A{row_number}", [row_values]))
    _invalidate_cache(tab_name)


def delete_row(tab_name: str, row_number: int) -> None:
    with_retry(lambda: get_worksheet(tab_name).delete_rows(row_number))
    _invalidate_cache(tab_name)


def _column_letter(index: int) -> str:
    """Converte un indice di colonna 0-based nella lettera A1 corrispondente (0 -> A, 1 -> B, ...)."""
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def update_cell_by_header(tab_name: str, row_number: int, header: str, value) -> None:
    """Aggiorna una singola cella individuata per nome colonna, senza toccare le altre."""
    headers = config.SHEET_STRUCTURE[tab_name]
    col_letter = _column_letter(headers.index(header))
    with_retry(lambda: get_worksheet(tab_name).update(f"{col_letter}{row_number}", [[value]]))
    _invalidate_cache(tab_name)
