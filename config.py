import json
import os

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ["SECRET_KEY"]
APP_PASSWORD_HASH = os.environ["APP_PASSWORD_HASH"]

# Render imposta automaticamente RENDER=true su ogni servizio: usato per capire
# se siamo online (cookie di sessione solo via HTTPS) o in sviluppo locale
# (dove il server gira in HTTP semplice e un cookie "solo HTTPS" impedirebbe il login).
IS_PRODUCTION = os.environ.get("RENDER") is not None

GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_CALENDAR_ID = os.environ["GOOGLE_CALENDAR_ID"]

CALENDAR_IGNORE_KEYWORDS = [
    kw.strip()
    for kw in os.environ.get("CALENDAR_IGNORE_KEYWORDS", "").split(",")
    if kw.strip()
]

GOOGLE_API_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def load_service_account_info() -> dict:
    """Restituisce le credenziali della service account come dict.

    Supporta due modalità, in questo ordine di priorità:
    - GOOGLE_SERVICE_ACCOUNT_JSON: contenuto JSON completo come stringa (usato su Render)
    - GOOGLE_SERVICE_ACCOUNT_FILE: percorso a un file .json locale (comodo in sviluppo)
    """
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw_json:
        return json.loads(raw_json)

    file_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise RuntimeError(
        "Nessuna credenziale service account trovata: imposta "
        "GOOGLE_SERVICE_ACCOUNT_JSON oppure GOOGLE_SERVICE_ACCOUNT_FILE."
    )


# Nomi dei tab nel Google Sheet: unica fonte di verità, usata da tutta l'app.
TAB_PAZIENTI = "Pazienti"
TAB_PIATTAFORME = "Piattaforme"
TAB_TIPI_PRESTAZIONE = "Tipi_Prestazione"
TAB_VOCI_COSTO = "Voci_Costo"
TAB_ANAGRAFICA_RICAVI = "Anagrafica_Ricavi"
TAB_ANAGRAFICA_COSTI = "Anagrafica_Costi"
TAB_COSTI_FISSI = "Costi_Fissi"
TAB_MOVIMENTI = "Movimenti"
TAB_EVENTI_PROCESSATI = "Eventi_processati"

SHEET_STRUCTURE = {
    TAB_PAZIENTI: ["Nome", "Contatto"],
    TAB_PIATTAFORME: ["Nome"],
    TAB_TIPI_PRESTAZIONE: ["Nome"],
    TAB_VOCI_COSTO: ["Nome"],
    TAB_ANAGRAFICA_RICAVI: ["Piattaforma", "Tipo prestazione", "Prezzo lordo"],
    TAB_COSTI_FISSI: ["Nome", "Importo mensile", "Data inizio", "Data fine"],
    TAB_ANAGRAFICA_COSTI: [
        "Piattaforma",
        "Tipo prestazione",
        "Voce di costo",
        "Tipo costo",
        "Valore",
    ],
    TAB_MOVIMENTI: [
        "Data",
        "Paziente",
        "Piattaforma",
        "Tipo prestazione",
        "Importo lordo",
        "Costo",
        "Importo netto",
        "Stato pagamento",
        "Metodo pagamento",
        "Note",
    ],
    TAB_EVENTI_PROCESSATI: ["ID evento", "Data processamento", "Stato"],
}
