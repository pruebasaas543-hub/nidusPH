"""
app/configuracion/apariencias/routes.py
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.configuracion.apariencias.controller import AparienciaController

apariencias_bp = Blueprint("config_apariencias", __name__, url_prefix="/config")


@apariencias_bp.route("/apariencias", methods=["GET"])
def listar():
    _, data = AparienciaController.listar()
    return ok(serializar(data))


@apariencias_bp.route("/apariencias/<apariencia_id>", methods=["GET"])
def obtener(apariencia_id):
    exito, resultado = AparienciaController.obtener(apariencia_id)
    if not exito:
        return err(resultado)
    return ok(serializar(resultado))


@apariencias_bp.route("/apariencias", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = AparienciaController.crear(datos)
    if not exito:
        return err(resultado)
    return ok(resultado)


@apariencias_bp.route("/apariencias/<apariencia_id>", methods=["PUT"])
@requiere_superadmin
def actualizar(apariencia_id):
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = AparienciaController.actualizar(apariencia_id, datos)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@apariencias_bp.route("/apariencias/<apariencia_id>", methods=["DELETE"])
@requiere_superadmin
def eliminar(apariencia_id):
    exito, resultado = AparienciaController.eliminar(apariencia_id)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@apariencias_bp.route("/apariencias/sembrar", methods=["POST"])
@requiere_superadmin
def sembrar():
    from app.configuracion.apariencias.model import AparienciaModel
    insertados = AparienciaModel.sembrar_predeterminados()
    return ok(mensaje=f"Siembra completada: {insertados} apariencia(s) insertada(s)")
