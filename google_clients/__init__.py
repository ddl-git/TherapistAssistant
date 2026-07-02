import time


def with_retry(fn, tentativi: int = 3, attesa_secondi: float = 1.0):
    """Esegue fn() ritentando su errori di rete transitori (es. connessione
    interrotta a metà chiamata verso le API Google), invece di far fallire
    subito la richiesta con un errore che in realtà si sarebbe risolto da solo.
    """
    ultimo_errore = None
    for tentativo in range(tentativi):
        try:
            return fn()
        except (ConnectionError, OSError, TimeoutError) as exc:
            ultimo_errore = exc
            if tentativo < tentativi - 1:
                time.sleep(attesa_secondi)
    raise ultimo_errore
