"""
app/configuracion/apariencia_empresa/routes.py
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.configuracion.apariencia_empresa.controller import AparienciaEmpresaController

apariencia_empresa_bp = Blueprint("config_apariencia_empresa", __name__, url_prefix="/config")


@apariencia_empresa_bp.route("/apariencia-empresa", methods=["GET"])
@requiere_superadmin
def listar():
    _, data = AparienciaEmpresaController.listar()
    return ok(serializar(data))


@apariencia_empresa_bp.route("/apariencia-empresa/<empresa_id>", methods=["GET"])
@requiere_superadmin
def listar_por_empresa(empresa_id):
    exito, resultado = AparienciaEmpresaController.listar_por_empresa(empresa_id)
    if not exito:
        return err(resultado)
    return ok(serializar(resultado))


@apariencia_empresa_bp.route("/apariencia-empresa", methods=["POST"])
@requiere_superadmin
def asociar():
    body          = request.get_json(silent=True) or {}
    empresa_id    = (body.get("empresa_id") or "").strip()
    apariencia_ids = body.get("apariencia_ids", [])
    if isinstance(apariencia_ids, str):
        apariencia_ids = [apariencia_ids]
    exito, resultado = AparienciaEmpresaController.asociar_multiples(
        empresa_id, apariencia_ids, session.get("num_doc", "")
    )
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@apariencia_empresa_bp.route("/apariencia-empresa/personalizado", methods=["POST"])
@requiere_superadmin
def crear_y_asociar():
    body       = request.get_json(silent=True) or {}
    empresa_id = (body.get("empresa_id") or "").strip()
    datos      = body.get("apariencia", {})
    exito, resultado = AparienciaEmpresaController.crear_y_asociar(
        empresa_id, datos, session.get("num_doc", "")
    )
    if not exito:
        return err(resultado)
    return ok(resultado)


@apariencia_empresa_bp.route("/apariencia-empresa/<empresa_id>/<apariencia_id>", methods=["DELETE"])
@requiere_superadmin
def desasociar(empresa_id, apariencia_id):
    exito, resultado = AparienciaEmpresaController.desasociar_uno(empresa_id, apariencia_id)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)
