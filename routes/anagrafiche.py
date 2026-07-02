from flask import Blueprint, redirect, render_template, request, url_for

from auth import login_required
from services import anagrafica_service

bp = Blueprint("anagrafiche", __name__, url_prefix="/anagrafiche")


@bp.route("/")
@login_required
def index():
    return render_template("anagrafiche/index.html")


@bp.route("/pazienti", methods=["GET", "POST"])
@login_required
def pazienti():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        contatto = request.form.get("contatto", "").strip()
        row = request.form.get("row")
        if row:
            anagrafica_service.update_paziente(int(row), nome, contatto)
        else:
            anagrafica_service.add_paziente(nome, contatto)
        return redirect(url_for("anagrafiche.pazienti"))

    righe = anagrafica_service.list_pazienti()
    edit_row = request.args.get("edit", type=int)
    editing = next((r for r in righe if r["_row"] == edit_row), None) if edit_row else None
    return render_template("anagrafiche/pazienti.html", righe=righe, editing=editing)


@bp.route("/piattaforme", methods=["GET", "POST"])
@login_required
def piattaforme():
    anagrafica_service.seed_piattaforme_e_tipi_da_tariffario()
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        if nome:
            anagrafica_service.add_piattaforma(nome)
        return redirect(url_for("anagrafiche.piattaforme"))

    return render_template("anagrafiche/piattaforme.html", righe=anagrafica_service.list_piattaforme())


@bp.route("/piattaforme/<int:row>/elimina", methods=["POST"])
@login_required
def elimina_piattaforma(row):
    anagrafica_service.delete_piattaforma(row)
    return redirect(url_for("anagrafiche.piattaforme"))


@bp.route("/tipi-prestazione", methods=["GET", "POST"])
@login_required
def tipi_prestazione():
    anagrafica_service.seed_piattaforme_e_tipi_da_tariffario()
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        if nome:
            anagrafica_service.add_tipo_prestazione(nome)
        return redirect(url_for("anagrafiche.tipi_prestazione"))

    return render_template("anagrafiche/tipi_prestazione.html", righe=anagrafica_service.list_tipi_prestazione())


@bp.route("/tipi-prestazione/<int:row>/elimina", methods=["POST"])
@login_required
def elimina_tipo_prestazione(row):
    anagrafica_service.delete_tipo_prestazione(row)
    return redirect(url_for("anagrafiche.tipi_prestazione"))


@bp.route("/voci-costo", methods=["GET", "POST"])
@login_required
def voci_costo():
    anagrafica_service.seed_voci_costo_default()
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        if nome:
            anagrafica_service.add_voce_costo(nome)
        return redirect(url_for("anagrafiche.voci_costo"))

    return render_template("anagrafiche/voci_costo.html", righe=anagrafica_service.list_voci_costo())


@bp.route("/voci-costo/<int:row>/elimina", methods=["POST"])
@login_required
def elimina_voce_costo(row):
    anagrafica_service.delete_voce_costo(row)
    return redirect(url_for("anagrafiche.voci_costo"))


@bp.route("/ricavi", methods=["GET", "POST"])
@login_required
def ricavi():
    anagrafica_service.seed_piattaforme_e_tipi_da_tariffario()
    if request.method == "POST":
        piattaforma = request.form.get("piattaforma", "").strip()
        tipo_prestazione = request.form.get("tipo_prestazione", "").strip()
        prezzo_lordo = request.form.get("prezzo_lordo", "0").replace(",", ".")
        row = request.form.get("row")
        if row:
            anagrafica_service.update_ricavo(int(row), piattaforma, tipo_prestazione, prezzo_lordo)
        else:
            anagrafica_service.add_ricavo(piattaforma, tipo_prestazione, prezzo_lordo)
        return redirect(url_for("anagrafiche.ricavi"))

    righe = anagrafica_service.list_ricavi()
    edit_row = request.args.get("edit", type=int)
    editing = next((r for r in righe if r["_row"] == edit_row), None) if edit_row else None
    return render_template(
        "anagrafiche/ricavi.html",
        righe=righe,
        editing=editing,
        piattaforme=anagrafica_service.list_piattaforme(),
        tipi_prestazione=anagrafica_service.list_tipi_prestazione(),
    )


@bp.route("/ricavi/<int:row>/elimina", methods=["POST"])
@login_required
def elimina_ricavo(row):
    anagrafica_service.delete_ricavo(row)
    return redirect(url_for("anagrafiche.ricavi"))


@bp.route("/costi", methods=["GET", "POST"])
@login_required
def costi():
    anagrafica_service.seed_piattaforme_e_tipi_da_tariffario()
    anagrafica_service.seed_voci_costo_default()
    if request.method == "POST":
        piattaforma = request.form.get("piattaforma", "").strip()
        tipo_prestazione = request.form.get("tipo_prestazione", "").strip()
        voce_costo = request.form.get("voce_costo", "").strip()
        tipo_costo = request.form.get("tipo_costo", "percentuale")
        valore = request.form.get("valore", "0").replace(",", ".")
        row = request.form.get("row")
        if row:
            anagrafica_service.update_costo(int(row), piattaforma, tipo_prestazione, voce_costo, tipo_costo, valore)
        else:
            anagrafica_service.add_costo(piattaforma, tipo_prestazione, voce_costo, tipo_costo, valore)
        return redirect(url_for("anagrafiche.costi"))

    righe = anagrafica_service.list_costi()
    edit_row = request.args.get("edit", type=int)
    editing = next((r for r in righe if r["_row"] == edit_row), None) if edit_row else None
    return render_template(
        "anagrafiche/costi.html",
        righe=righe,
        editing=editing,
        piattaforme=anagrafica_service.list_piattaforme(),
        tipi_prestazione=anagrafica_service.list_tipi_prestazione(),
        voci_costo=anagrafica_service.list_voci_costo(),
    )


@bp.route("/costi/<int:row>/elimina", methods=["POST"])
@login_required
def elimina_costo(row):
    anagrafica_service.delete_costo(row)
    return redirect(url_for("anagrafiche.costi"))


@bp.route("/costi-fissi", methods=["GET", "POST"])
@login_required
def costi_fissi():
    anagrafica_service.seed_piattaforme_e_tipi_da_tariffario()
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        piattaforma = request.form.get("piattaforma", "").strip()
        tipo_prestazione = request.form.get("tipo_prestazione", "").strip()
        importo_mensile = request.form.get("importo_mensile", "0").replace(",", ".")
        data_inizio = request.form.get("data_inizio", "")
        data_fine = request.form.get("data_fine", "")
        row = request.form.get("row")
        if row:
            anagrafica_service.update_costo_fisso(
                int(row), nome, piattaforma, tipo_prestazione, importo_mensile, data_inizio, data_fine
            )
        else:
            anagrafica_service.add_costo_fisso(
                nome, piattaforma, tipo_prestazione, importo_mensile, data_inizio, data_fine
            )
        return redirect(url_for("anagrafiche.costi_fissi"))

    righe = anagrafica_service.list_costi_fissi()
    edit_row = request.args.get("edit", type=int)
    duplica_row = request.args.get("duplica", type=int)
    editing = next((r for r in righe if r["_row"] == edit_row), None) if edit_row else None
    duplicando = next((r for r in righe if r["_row"] == duplica_row), None) if duplica_row else None
    return render_template(
        "anagrafiche/costi_fissi.html",
        righe=righe,
        editing=editing,
        duplicando=duplicando,
        piattaforme=anagrafica_service.list_piattaforme(),
        tipi_prestazione=anagrafica_service.list_tipi_prestazione(),
    )


@bp.route("/costi-fissi/<int:row>/elimina", methods=["POST"])
@login_required
def elimina_costo_fisso(row):
    anagrafica_service.delete_costo_fisso(row)
    return redirect(url_for("anagrafiche.costi_fissi"))
