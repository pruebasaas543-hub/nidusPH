"""
app/contabilidad/presupuesto/routes.py
────────────────────────────────────────
Blueprint Flask para presupuesto anual.
Prefijo: /cont
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.contabilidad.presupuesto.controller import PresupuestoController

presupuesto_bp = Blueprint("cont_presupuesto", __name__, url_prefix="/cont")


@presupuesto_bp.route("/presupuesto/<empresa_id>/<int:anio>", methods=["GET"])
@requiere_superadmin
def obtener(empresa_id, anio):
    exito, data = PresupuestoController.obtener(empresa_id, anio)
    if not exito:
        return err(data, 404)
    return ok(serializar(data))


@presupuesto_bp.route("/presupuesto", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or ""
    exito, resultado = PresupuestoController.crear(datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(resultado)


@presupuesto_bp.route("/presupuesto/<presupuesto_id>/linea", methods=["PUT"])
@requiere_superadmin
def actualizar_linea(presupuesto_id):
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or ""
    exito, resultado = PresupuestoController.actualizar_linea(
        presupuesto_id, datos, session.get("num_doc", ""), ip
    )
    if not exito:
        return err(resultado)
    return ok(resultado if isinstance(resultado, dict) else None, mensaje=resultado if isinstance(resultado, str) else None)
