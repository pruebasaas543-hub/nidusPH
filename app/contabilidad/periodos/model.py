"""
app/contabilidad/periodos/model.py
────────────────────────────────────
Operaciones MongoDB para cont_periodos.
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col():
    return db["cont_periodos"]


class PeriodoModel:

    @staticmethod
    def crear(datos: dict) -> str:
        doc = {
            "empresa_id": datos["empresa_id"],
            "anio":       int(datos["anio"]),
            "mes":        int(datos["mes"]),
            "estado":     "abierto",
            "cerrado_por": None,
            "cerrado_en":  None,
            "creado_en":   datetime.utcnow(),
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def cerrar(periodo_id: str, cerrado_por: str):
        _col().update_one(
            {"_id": ObjectId(periodo_id)},
            {"$set": {
                "estado":     "cerrado",
                "cerrado_por": cerrado_por,
                "cerrado_en":  datetime.utcnow(),
            }}
        )

    @staticmethod
    def listar(empresa_id: str) -> list:
        return list(_col().find({"empresa_id": empresa_id}).sort([("anio", -1), ("mes", -1)]))

    @staticmethod
    def obtener(periodo_id: str):
        return _col().find_one({"_id": ObjectId(periodo_id)})

    @staticmethod
    def buscar(empresa_id: str, anio: int, mes: int):
        return _col().find_one({"empresa_id": empresa_id, "anio": anio, "mes": mes})
