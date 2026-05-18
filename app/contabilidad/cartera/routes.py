"""
app/contabilidad/cartera/routes.py
────────────────────────────────────
Blueprint Flask para cartera y acuerdos de pago.
Prefijo: /cont
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.contabilidad.cartera.controller import CarteraController

cartera_bp = Blueprint("cont_cartera", __name__, url_prefix="/cont")


@cartera_bp.route("/cartera/<empresa_id>", methods=["GET"])
@requiere_superadmin
def listar(empresa_id):
    filtros = {}
    if request.args.get("estado"):
        filtros["estado"] = request.args.get("estado")
    if request.args.get("vencimiento_hasta"):
        filtros["vencimiento_hasta"] = request.args.get("vencimiento_hasta")
    exito, data = CarteraController.listar(empresa_id, filtros)
    if not exito:
        return err(data)
    return ok(serializar(data))


@cartera_bp.route("/cartera", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or ""
    exito, resultado = CarteraController.crear(datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(resultado)


@cartera_bp.route("/cartera/<cartera_id>/mora", methods=["POST"])
@requiere_superadmin
def calcular_mora(cartera_id):
    ip = request.remote_addr or ""
    datos = request.get_json(silent=True) or {}
    tasa = datos.get("tasa_diaria")
    if tasa is not None:
        try:
            tasa = float(tasa)
        except (ValueError, TypeError):
            return err("tasa_diaria debe ser un número")
    exito, resultado = CarteraController.calcular_mora(
        cartera_id, session.get("num_doc", ""), ip, tasa
    )
    if not exito:
        return err(resultado, 400)
    return ok(resultado)


@cartera_bp.route("/acuerdos_pago", methods=["POST"])
@requiere_superadmin
def crear_acuerdo():
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or ""
    exito, resultado = CarteraController.crear_acuerdo(datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(resultado)


@cartera_bp.route("/acuerdos_pago/<empresa_id>", methods=["GET"])
@requiere_superadmin
def listar_acuerdos(empresa_id):
    exito, data = CarteraController.listar_acuerdos(empresa_id)
    if not exito:
        return err(data)
    return ok(serializar(data))
