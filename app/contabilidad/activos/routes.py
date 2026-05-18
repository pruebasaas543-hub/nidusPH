"""
app/contabilidad/activos/routes.py
────────────────────────────────────
Blueprint Flask para activos fijos.
Prefijo: /cont
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.contabilidad.activos.controller import ActivosController

activos_bp = Blueprint("cont_activos", __name__, url_prefix="/cont")


@activos_bp.route("/activos/<empresa_id>", methods=["GET"])
@requiere_superadmin
def listar(empresa_id):
    exito, data = ActivosController.listar(empresa_id)
    if not exito:
        return err(data)
    return ok(serializar(data))


@activos_bp.route("/activos", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or ""
    exito, resultado = ActivosController.crear(datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(resultado)


@activos_bp.route("/activos/<activo_id>", methods=["PUT"])
@requiere_superadmin
def actualizar(activo_id):
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or ""
    exito, resultado = ActivosController.actualizar(activo_id, datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@activos_bp.route("/activos/depreciar/<empresa_id>", methods=["POST"])
@requiere_superadmin
def batch_depreciacion(empresa_id):
    ip = request.remote_addr or ""
    exito, resultado = ActivosController.batch_depreciacion(
        empresa_id, session.get("num_doc", ""), ip
    )
    if not exito:
        return err(resultado, 400)
    return ok(resultado)
