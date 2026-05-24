"""
app/configuracion/empresas/routes.py
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.configuracion.empresas.controller import EmpresaController

empresas_bp = Blueprint("config_empresas", __name__, url_prefix="/config")


@empresas_bp.route("/empresas/catalogos", methods=["GET"])
@requiere_superadmin
def catalogos():
    exito, data = EmpresaController.obtener_catalogos()
    if not exito: return err(data)
    return ok(serializar(data))


@empresas_bp.route("/empresas/municipios/<path:nombre_depto>", methods=["GET"])
@requiere_superadmin
def municipios(nombre_depto):
    exito, data = EmpresaController.municipios_por_depto(nombre_depto)
    if not exito: return err(data)
    return ok(serializar(data))


@empresas_bp.route("/empresas", methods=["GET"])
@requiere_superadmin
def listar():
    _, data = EmpresaController.listar()
    return ok(serializar(data))


@empresas_bp.route("/empresas", methods=["POST"])
@requiere_superadmin
def crear():
    exito, resultado = EmpresaController.crear(
        request.form.to_dict(), request.files, creado_por=session["num_doc"]
    )
    if not exito: return err(resultado)
    return ok(resultado)


@empresas_bp.route("/empresas/<empresa_id>", methods=["GET"])
@requiere_superadmin
def obtener(empresa_id):
    from app.configuracion.empresas.model import EmpresaModel
    emp = EmpresaModel.buscar_por_id(empresa_id)
    if not emp: return err("Empresa no encontrada", 404)
    return ok(serializar(emp))


@empresas_bp.route("/empresas/<empresa_id>", methods=["PUT"])
@requiere_superadmin
def editar(empresa_id):
    datos = request.form.to_dict()
    datos.pop("nit", None)
    exito, resultado = EmpresaController.editar(empresa_id, datos, request.files or {})
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@empresas_bp.route("/empresas/<empresa_id>/estado", methods=["PATCH"])
@requiere_superadmin
def estado(empresa_id):
    body = request.get_json(silent=True) or {}
    activo             = bool(body.get("activo"))
    estado_contrato_id = body.get("estado_contrato_id") or None
    motivo             = body.get("motivo") or None
    exito, resultado   = EmpresaController.cambiar_estado(empresa_id, activo, estado_contrato_id, motivo)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@empresas_bp.route("/empresas/<empresa_id>/imagen/<campo>", methods=["GET"])
@requiere_superadmin
def imagen(empresa_id, campo):
    exito, resultado = EmpresaController.obtener_imagen(empresa_id, campo)
    if not exito: return err(resultado, 404)
    return ok(resultado)
