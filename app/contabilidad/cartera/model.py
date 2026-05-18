"""
app/contabilidad/cartera/model.py
───────────────────────────────────
Operaciones MongoDB para cont_cartera y cont_acuerdos_pago.
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col_cartera():
    return db["cont_cartera"]


def _col_acuerdos():
    return db["cont_acuerdos_pago"]


class CarteraModel:

    # ── Cartera ──────────────────────────────────────────────────────────────

    @staticmethod
    def crear(datos: dict) -> str:
        doc = {
            "empresa_id":        datos["empresa_id"],
            "unidad_id":         datos.get("unidad_id"),
            "concepto":          datos.get("concepto", "").strip(),
            "valor":             float(datos.get("valor", 0)),
            "fecha_vencimiento": datos.get("fecha_vencimiento"),
            "saldo_pendiente":   float(datos.get("valor", 0)),
            "mora_acumulada":    0.0,
            "estado":            "vigente",    # vigente / vencida / pagada
            "creado_en":         datetime.utcnow(),
        }
        return str(_col_cartera().insert_one(doc).inserted_id)

    @staticmethod
    def obtener(cartera_id: str):
        return _col_cartera().find_one({"_id": ObjectId(cartera_id)})

    @staticmethod
    def listar(empresa_id: str, filtros: dict = None) -> list:
        q = {"empresa_id": empresa_id}
        if filtros:
            if filtros.get("estado"):
                q["estado"] = filtros["estado"]
            if filtros.get("vencimiento_hasta"):
                q["fecha_vencimiento"] = {"$lte": filtros["vencimiento_hasta"]}
        return list(_col_cartera().find(q).sort("fecha_vencimiento", 1))

    @staticmethod
    def actualizar_mora(cartera_id: str, mora: float):
        _col_cartera().update_one(
            {"_id": ObjectId(cartera_id)},
            {"$set": {
                "mora_acumulada": mora,
                "estado": "vencida",
                "actualizado_en": datetime.utcnow(),
            }}
        )

    # ── Acuerdos de pago ─────────────────────────────────────────────────────

    @staticmethod
    def crear_acuerdo(datos: dict) -> str:
        doc = {
            "empresa_id":  datos["empresa_id"],
            "cartera_ids": datos.get("cartera_ids", []),
            "cuotas":      datos.get("cuotas", []),
            "estado":      "activo",    # activo / incumplido / cancelado
            "creado_en":   datetime.utcnow(),
        }
        return str(_col_acuerdos().insert_one(doc).inserted_id)

    @staticmethod
    def listar_acuerdos(empresa_id: str) -> list:
        return list(_col_acuerdos().find({"empresa_id": empresa_id}).sort("creado_en", -1))

    @staticmethod
    def obtener_acuerdo(acuerdo_id: str):
        return _col_acuerdos().find_one({"_id": ObjectId(acuerdo_id)})
