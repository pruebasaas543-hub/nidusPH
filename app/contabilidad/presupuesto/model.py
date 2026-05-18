"""
app/contabilidad/presupuesto/model.py
───────────────────────────────────────
Operaciones MongoDB para cont_presupuesto y cont_presupuesto_lineas.
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col_pres():
    return db["cont_presupuesto"]


def _col_lineas():
    return db["cont_presupuesto_lineas"]


class PresupuestoModel:

    # ── Cabecera presupuesto ──────────────────────────────────────────────────

    @staticmethod
    def crear(datos: dict) -> str:
        doc = {
            "empresa_id":   datos["empresa_id"],
            "anio":         int(datos["anio"]),
            "aprobado_por": datos.get("aprobado_por", ""),
            "aprobado_en":  datetime.utcnow(),
            "creado_en":    datetime.utcnow(),
        }
        return str(_col_pres().insert_one(doc).inserted_id)

    @staticmethod
    def obtener(empresa_id: str, anio: int):
        return _col_pres().find_one({"empresa_id": empresa_id, "anio": anio})

    @staticmethod
    def obtener_por_id(presupuesto_id: str):
        return _col_pres().find_one({"_id": ObjectId(presupuesto_id)})

    # ── Líneas de presupuesto ─────────────────────────────────────────────────

    @staticmethod
    def crear_linea(presupuesto_id: str, linea: dict) -> str:
        doc = {
            "presupuesto_id": presupuesto_id,
            "cuenta_id":      linea["cuenta_id"],
            "valores_mes":    [float(v) for v in linea.get("valores_mes", [0] * 12)],
            "ejecutado_mes":  [0.0] * 12,
        }
        return str(_col_lineas().insert_one(doc).inserted_id)

    @staticmethod
    def actualizar_linea(linea_id: str, datos: dict):
        campos = {}
        if "valores_mes" in datos:
            campos["valores_mes"] = [float(v) for v in datos["valores_mes"]]
        if "ejecutado_mes" in datos:
            campos["ejecutado_mes"] = [float(v) for v in datos["ejecutado_mes"]]
        if campos:
            _col_lineas().update_one(
                {"_id": ObjectId(linea_id)},
                {"$set": {**campos, "actualizado_en": datetime.utcnow()}}
            )

    @staticmethod
    def listar_lineas(presupuesto_id: str) -> list:
        return list(_col_lineas().find({"presupuesto_id": presupuesto_id}))
