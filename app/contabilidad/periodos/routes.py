"""
app/contabilidad/periodos/routes.py
─────────────────────────────────────
Blueprint Flask para periodos contables.
Prefijo: /cont
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.contabilidad.periodos.controller import PeriodoController

periodos_bp = Blueprint("cont_periodos", __name__, url_prefix="/cont")


@periodos_bp.route("/periodos/<empresa_id>", methods=["GET"])
@requiere_superadmin
def listar(empresa_id):
    exito, data = PeriodoController.listar(empresa_id)
    if not exito:
        return err(data)
    return ok(serializar(data))


@periodos_bp.route("/periodos", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or ""
    exito, resultado = PeriodoController.crear(datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(resultado)


@periodos_bp.route("/periodos/<periodo_id>/cerrar", methods=["POST"])
@requiere_superadmin
def cerrar(periodo_id):
    ip = request.remote_addr or ""
    exito, resultado = PeriodoController.cerrar(periodo_id, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado, 400)
    return ok(mensaje=resultado)
