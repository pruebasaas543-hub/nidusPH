"""
app/configuracion/asociaciones/routes.py
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.configuracion.asociaciones.controller import AsociacionController

asociaciones_bp = Blueprint("config_asociaciones", __name__, url_prefix="/config")


@asociaciones_bp.route("/asociaciones", methods=["GET"])
@requiere_superadmin
def listar():
    _, data = AsociacionController.listar_todas()
    return ok(serializar(data))

@asociaciones_bp.route("/asociaciones/empresa/<empresa_id>", methods=["GET"])
@requiere_superadmin
def por_empresa(empresa_id):
    exito, data = AsociacionController.listar_por_empresa(empresa_id)
    if not exito: return err(data)
    return ok(serializar(data))

@asociaciones_bp.route("/asociaciones/disponibles", methods=["GET"])
@requiere_superadmin
def disponibles():
    _, data = AsociacionController.listar_usuarios_disponibles()
    return ok(serializar(data))

@asociaciones_bp.route("/asociaciones", methods=["POST"])
@requiere_superadmin
def vincular():
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = AsociacionController.vincular(datos, session["num_doc"])
    if not exito: return err(resultado)
    return ok(resultado)

@asociaciones_bp.route("/asociaciones/usuario/<user_id>", methods=["GET"])
@requiere_superadmin
def por_usuario(user_id):
    _, data = AsociacionController.listar_por_usuario(user_id)
    return ok(serializar(data))


@asociaciones_bp.route("/asociaciones/<asoc_id>", methods=["PUT"])
@requiere_superadmin
def editar(asoc_id):
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = AsociacionController.editar(asoc_id, datos)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@asociaciones_bp.route("/asociaciones/<asoc_id>", methods=["DELETE"])
@requiere_superadmin
def desvincular(asoc_id):
    _, resultado = AsociacionController.desvincular(asoc_id)
    return ok(mensaje=resultado)
