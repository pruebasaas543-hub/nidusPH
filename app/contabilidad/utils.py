"""
app/contabilidad/utils.py
─────────────────────────
Helpers compartidos por todos los sub-módulos de contabilidad.
"""

from datetime import datetime
from bson import ObjectId
from app import db


def audit_log(
    empresa_id: str,
    usuario_id: str,
    accion: str,
    modulo: str,
    ref_id: str,
    ip: str,
    datos_antes=None,
    datos_despues=None,
):
    """Inserta un registro inmutable en cont_audit_log."""
    doc = {
        "empresa_id":    empresa_id,
        "usuario_id":    usuario_id,
        "accion":        accion,
        "modulo":        modulo,
        "ref_id":        str(ref_id) if ref_id else None,
        "datos_antes":   datos_antes,
        "datos_despues": datos_despues,
        "ip":            ip,
        "timestamp":     datetime.utcnow(),
    }
    db["cont_audit_log"].insert_one(doc)


def verificar_periodo_abierto(empresa_id: str, anio: int, mes: int):
    """
    Comprueba si el periodo contable está abierto.

    Retorna:
        (True,  periodo_id_str)   — si el periodo existe y está abierto.
        (False, mensaje_error)    — si está cerrado o no existe.
    """
    periodo = db["cont_periodos"].find_one(
        {"empresa_id": empresa_id, "anio": anio, "mes": mes}
    )
    if not periodo:
        return False, f"No existe periodo contable para {anio}-{mes:02d}"
    if periodo.get("estado") != "abierto":
        return False, f"El periodo {anio}-{mes:02d} está cerrado"
    return True, str(periodo["_id"])
