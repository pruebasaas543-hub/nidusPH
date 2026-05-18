"""
app/contabilidad/comprobantes/routes.py
─────────────────────────────────────────
Blueprint Flask para comprobantes de diario.
Prefijo: /cont
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.contabilidad.comprobantes.controller import ComprobantesController

comprobantes_bp = Blueprint("cont_comprobantes", __name__, url_prefix="/cont")


@comprobantes_bp.route("/comprobantes/<empresa_id>", methods=["GET"])
@requiere_superadmin
def listar(empresa_id):
    filtros = {}
    for campo in ("fecha_desde", "fecha_hasta", "tipo", "estado"):
        if request.args.get(campo):
            filtros[campo] = request.args.get(campo)
    exito, data = ComprobantesController.listar(empresa_id, filtros)
    if not exito:
        return err(data)
    return ok(serializar(data))


@comprobantes_bp.route("/comprobantes", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or ""
    exito, resultado = ComprobantesController.crear(datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(resultado)


@comprobantes_bp.route("/comprobantes/<comprobante_id>/asentar", methods=["POST"])
@requiere_superadmin
def asentar(comprobante_id):
    ip = request.remote_addr or ""
    exito, resultado = ComprobantesController.asentar(
        comprobante_id, session.get("num_doc", ""), ip
    )
    if not exito:
        return err(resultado, 400)
    return ok(resultado)


@comprobantes_bp.route("/comprobantes/<comprobante_id>", methods=["GET"])
@requiere_superadmin
def obtener(comprobante_id):
    exito, data = ComprobantesController.obtener_con_asientos(comprobante_id)
    if not exito:
        return err(data, 404)
    return ok(serializar(data))
