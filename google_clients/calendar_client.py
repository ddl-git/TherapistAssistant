import datetime

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import config
from google_clients import with_retry

_service = None


def get_service():
    global _service
    if _service is None:
        creds = Credentials.from_service_account_info(
            config.load_service_account_info(), scopes=config.GOOGLE_API_SCOPES
        )
        _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return _service


def list_upcoming_events(max_results: int = 10, days_back: int = 30) -> list[dict]:
    """Elenca gli eventi dal Calendar configurato, da `days_back` giorni fa in poi.

    Usata per la Fase 1 (test di connessione). La logica di sync/filtro
    per la coda di validazione arriva in Fase 2.
    """
    service = get_service()
    time_min = (
        datetime.datetime.utcnow() - datetime.timedelta(days=days_back)
    ).isoformat() + "Z"

    events_result = with_retry(
        lambda: service.events()
        .list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events_result.get("items", [])
