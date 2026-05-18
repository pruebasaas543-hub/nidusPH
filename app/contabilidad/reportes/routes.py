"""
app/contabilidad/reportes/routes.py
─────────────────────────────────────
Blueprint Flask para reportes financieros.
Prefijo: /cont
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.contabilidad.reportes.controller import ReportesController

reportes_bp = Blueprint("cont_reportes", __name__, url_prefix="/cont")


@reportes_bp.route("/reportes/balance_general/<empresa_id>", methods=["GET"])
@requiere_superadmin
def balance_general(empresa_id):
    exito, data = ReportesController.balance_general(empresa_id)
    if not exito:
        return err(data)
    return ok(serializar(data))


@reportes_bp.route("/reportes/estado_resultados/<empresa_id>", methods=["GET"])
@requiere_superadmin
def estado_resultados(empresa_id):
    exito, data = ReportesController.estado_resultados(empresa_id)
    if not exito:
        return err(data)
    return ok(serializar(data))


@reportes_bp.route("/reportes/auxiliar/<empresa_id>/<cuenta_id>", methods=["GET"])
@requiere_superadmin
def auxiliar_cuenta(empresa_id, cuenta_id):
    exito, data = ReportesController.auxiliar_cuenta(empresa_id, cuenta_id)
    if not exito:
        return err(data)
    return ok(serializar(data))


@reportes_bp.route("/reportes/dashboard/<empresa_id>", methods=["GET"])
@requiere_superadmin
def dashboard(empresa_id):
    exito, data = ReportesController.dashboard(empresa_id)
    if not exito:
        return err(data)
    return ok(serializar(data))
