"""
app/contabilidad/tesoreria/routes.py
──────────────────────────────────────
Blueprint Flask para tesorería (cuentas por pagar).
Prefijo: /cont
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.contabilidad.tesoreria.controller import TesoreriaController

tesoreria_bp = Blueprint("cont_tesoreria", __name__, url_prefix="/cont")


@tesoreria_bp.route("/facturas_proveedor/<empresa_id>", methods=["GET"])
@requiere_superadmin
def listar_facturas(empresa_id):
    exito, data = TesoreriaController.listar_facturas(empresa_id)
    if not exito:
        return err(data)
    return ok(serializar(data))


@tesoreria_bp.route("/facturas_proveedor", methods=["POST"])
@requiere_superadmin
def radicar_factura():
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or ""
    exito, resultado = TesoreriaController.radicar_factura(datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(resultado)


@tesoreria_bp.route("/facturas_proveedor/<factura_id>/aprobar", methods=["POST"])
@requiere_superadmin
def aprobar_factura(factura_id):
    ip = request.remote_addr or ""
    exito, resultado = TesoreriaController.aprobar_factura(
        factura_id, session.get("num_doc", ""), ip
    )
    if not exito:
        return err(resultado, 400)
    return ok(mensaje=resultado)


@tesoreria_bp.route("/facturas_proveedor/<factura_id>/pagar", methods=["POST"])
@requiere_superadmin
def registrar_pago(factura_id):
    ip = request.remote_addr or ""
    exito, resultado = TesoreriaController.registrar_pago(
        factura_id, session.get("num_doc", ""), ip
    )
    if not exito:
        return err(resultado, 400)
    return ok(mensaje=resultado)


@tesoreria_bp.route("/programacion_pagos/<empresa_id>", methods=["GET"])
@requiere_superadmin
def listar_programacion(empresa_id):
    exito, data = TesoreriaController.listar_programacion(empresa_id)
    if not exito:
        return err(data)
    return ok(serializar(data))


@tesoreria_bp.route("/programacion_pagos", methods=["POST"])
@requiere_superadmin
def programar_pago():
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or ""
    exito, resultado = TesoreriaController.programar_pago(datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(resultado)
