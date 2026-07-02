import time

from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

import config

bp = Blueprint("auth", __name__)

MAX_TENTATIVI = 5
BLOCCO_SECONDI = 300  # 5 minuti

# In memoria, per IP: (numero di fallimenti consecutivi, timestamp dell'ultimo fallimento).
# Basta per un'app mono-processo come questa; si resetta ad ogni riavvio del server.
_tentativi_falliti: dict[str, tuple[int, float]] = {}


def _bloccato(ip: str) -> bool:
    voce = _tentativi_falliti.get(ip)
    if not voce:
        return False
    count, ultimo_fallimento = voce
    if count < MAX_TENTATIVI:
        return False
    return (time.time() - ultimo_fallimento) < BLOCCO_SECONDI


def _registra_fallimento(ip: str) -> None:
    count, _ = _tentativi_falliti.get(ip, (0, 0.0))
    _tentativi_falliti[ip] = (count + 1, time.time())


def _reset_tentativi(ip: str) -> None:
    _tentativi_falliti.pop(ip, None)


@bp.route("/login", methods=["GET", "POST"])
def login():
    ip = request.remote_addr or "sconosciuto"

    if request.method == "POST":
        if _bloccato(ip):
            return render_template(
                "login.html",
                error="Troppi tentativi falliti. Riprova tra qualche minuto.",
            ), 429

        password = request.form.get("password", "")
        if check_password_hash(config.APP_PASSWORD_HASH, password):
            _reset_tentativi(ip)
            session["logged_in"] = True
            return redirect(url_for("main.test_connection"))

        _registra_fallimento(ip)
        return render_template("login.html", error="Password errata")

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
