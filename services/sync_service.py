from datetime import datetime

import config
from google_clients import calendar_client, sheets_client
from services import anagrafica_service


def get_processed_event_ids() -> set[str]:
    records = sheets_client.get_all_records(config.TAB_EVENTI_PROCESSATI)
    return {str(r.get("ID evento", "")).strip() for r in records if r.get("ID evento")}


def is_candidate_event(title: str, keywords: set[str]) -> bool:
    """Un evento è candidato per la coda se il titolo contiene il nome di una
    piattaforma o di un tipo prestazione già configurato nel tariffario
    (Anagrafica_Ricavi), es. 'Unobravo' in 'Unobravo - Seduta di terapia' o
    'Coaching' in 'Coaching 3 Dario'.

    Nota: un semplice trattino nel titolo NON basta da solo (troppo generico:
    prende anche eventi come colloqui di lavoro con un ' - ' nel titolo).
    Finché il tariffario è vuoto, la coda risulta vuota: va popolato con
    almeno una riga (piattaforma/tipo prestazione) perché il filtro trovi
    qualcosa da mostrare.
    """
    if not title or not keywords:
        return False
    lowered = title.lower()
    if any(ignore.lower() in lowered for ignore in config.CALENDAR_IGNORE_KEYWORDS):
        return False
    return any(keyword and keyword in lowered for keyword in keywords)


def guess_patient_name(title: str, keywords: set[str]) -> str:
    """Ipotesi sul nome paziente dal titolo evento, sempre modificabile
    dall'utente nel form di validazione (mai vincolante).

    Divide il titolo su ' - ' in segmenti e scarta quelli che corrispondono a
    una piattaforma o tipo prestazione già noti (Anagrafica_Ricavi): quello
    che resta è il nome paziente. Funziona sia con 2 segmenti
    ('Serenis - Mario Rossi') sia con 3 ('Serenis - Percorso - Mario Rossi'),
    prendendo l'ultimo segmento non riconosciuto come parola chiave.
    """
    if " - " not in title:
        return title.strip()
    segmenti = [s.strip() for s in title.split(" - ")]
    candidati = [s for s in segmenti if s.lower() not in keywords]
    return candidati[-1] if candidati else ""


def find_matching_combo(title: str, combos: list[dict]):
    """Cerca tra le combinazioni piattaforma+tipo prestazione (Anagrafica_Ricavi)
    quella più probabile per il titolo dell'evento, per precompilare il form di
    validazione (sempre sovrascrivibile).

    Se il titolo usa il formato 'Piattaforma - Tipo prestazione - Paziente', il
    primo segmento è trattato come la piattaforma dichiarata esplicitamente: se
    non corrisponde a nessuna piattaforma nota, non si propone nulla (meglio
    lasciar scegliere che indovinare una piattaforma diversa da quella scritta,
    es. 'Studio - Prima seduta - Andrea' non deve proporre 'Serenis' solo
    perché 'Prima seduta' esiste per Serenis).
    """
    if " - " in title:
        segmenti = [s.strip().lower() for s in title.split(" - ")]
        piattaforma_titolo = segmenti[0]
        combo_piattaforma = [
            c for c in combos if c["value"].partition("::")[0].lower() == piattaforma_titolo
        ]
        if not combo_piattaforma:
            return None

        resto = " ".join(segmenti[1:])
        for c in combo_piattaforma:
            tipo = c["value"].partition("::")[2].lower()
            if tipo and tipo in resto:
                return c

        if len(combo_piattaforma) == 1 and len(segmenti) == 2:
            return combo_piattaforma[0]

        return None

    # Titolo senza trattino (es. 'Coaching 3 Dario'): nessuna piattaforma
    # dichiarata esplicitamente, si cerca liberamente per parole chiave.
    lowered = title.lower()

    for combo in combos:
        piattaforma, _, tipo = combo["value"].partition("::")
        if piattaforma and tipo and piattaforma.lower() in lowered and tipo.lower() in lowered:
            return combo

    for combo in combos:
        _, _, tipo = combo["value"].partition("::")
        if tipo and tipo.lower() in lowered:
            return combo

    for combo in combos:
        piattaforma, _, _ = combo["value"].partition("::")
        if piattaforma and piattaforma.lower() in lowered:
            return combo

    return None


def mark_event_ignored(event_id: str) -> None:
    sheets_client.append_row(
        config.TAB_EVENTI_PROCESSATI,
        [event_id, datetime.now().isoformat(timespec="seconds"), "ignorato"],
    )


def list_queue_events() -> list[dict]:
    """Eventi calendario candidati (appuntamenti pazienti) non ancora processati."""
    processed_ids = get_processed_event_ids()
    keywords = anagrafica_service.keyword_whitelist()
    events = calendar_client.list_upcoming_events(max_results=250, days_back=90)

    queue = []
    for event in events:
        event_id = event.get("id")
        title = event.get("summary", "")
        if not event_id or event_id in processed_ids:
            continue
        if not is_candidate_event(title, keywords):
            continue
        start = event.get("start", {})
        queue.append(
            {
                "id": event_id,
                "title": title,
                "start": start.get("dateTime") or start.get("date"),
            }
        )
    return queue
