"""
app/configuracion/pagos/routes.py
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.configuracion.pagos.controller import AsociacionDatosPagoController

pagos_bp = Blueprint("config_pagos", __name__, url_prefix="/config")


@pagos_bp.route("/asociacion_pago/<empresa_id>", methods=["GET"])
@requiere_superadmin
def listar(empresa_id):
    exito, lista = AsociacionDatosPagoController.listar_por_empresa(empresa_id)
    if not exito: return err(lista)
    return ok(serializar(lista))


@pagos_bp.route("/asociacion_pago/<empresa_id>/<tipo>", methods=["GET"])
@requiere_superadmin
def listar_por_tipo(empresa_id, tipo):
    exito, lista = AsociacionDatosPagoController.listar_por_tipo(empresa_id, tipo)
    if not exito: return err(lista)
    return ok(serializar(lista))


@pagos_bp.route("/asociacion_pago/<empresa_id>/<tipo>", methods=["POST"])
@requiere_superadmin
def crear(empresa_id, tipo):
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = AsociacionDatosPagoController.crear(empresa_id, tipo, datos, session["num_doc"])
    if not exito: return err(resultado)
    return ok(resultado)


@pagos_bp.route("/asociacion_pago/<config_id>", methods=["PUT"])
@requiere_superadmin
def actualizar(config_id):
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = AsociacionDatosPagoController.actualizar(config_id, datos)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@pagos_bp.route("/asociacion_pago/<config_id>", methods=["DELETE"])
@requiere_superadmin
def eliminar(config_id):
    exito, resultado = AsociacionDatosPagoController.eliminar(config_id)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)
