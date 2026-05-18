"""
app/contabilidad/activos/model.py
───────────────────────────────────
Operaciones MongoDB para cont_activos_fijos.
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col():
    return db["cont_activos_fijos"]


class ActivosModel:

    @staticmethod
    def crear(datos: dict) -> str:
        valor_hist = float(datos.get("valor_historico", 0))
        vida_util  = int(datos.get("vida_util_meses", 1))
        doc = {
            "empresa_id":             datos["empresa_id"],
            "nombre":                 datos.get("nombre", "").strip(),
            "categoria":              datos.get("categoria", "").strip(),
            "fecha_compra":           datos.get("fecha_compra"),
            "valor_historico":        valor_hist,
            "vida_util_meses":        vida_util,
            "metodo_depreciacion":    datos.get("metodo_depreciacion", "linea_recta"),
            "depreciacion_acumulada": 0.0,
            "activo":                 True,
            "creado_en":              datetime.utcnow(),
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def obtener(activo_id: str):
        return _col().find_one({"_id": ObjectId(activo_id)})

    @staticmethod
    def listar(empresa_id: str) -> list:
        return list(_col().find({"empresa_id": empresa_id}).sort("nombre", 1))

    @staticmethod
    def actualizar(activo_id: str, datos: dict):
        campos = {}
        for campo in ("nombre", "categoria", "fecha_compra", "valor_historico",
                      "vida_util_meses", "metodo_depreciacion", "activo"):
            if campo in datos:
                campos[campo] = datos[campo]
        campos["actualizado_en"] = datetime.utcnow()
        _col().update_one({"_id": ObjectId(activo_id)}, {"$set": campos})

    @staticmethod
    def acumular_depreciacion(activo_id: str, monto_mensual: float):
        _col().update_one(
            {"_id": ObjectId(activo_id)},
            {
                "$inc": {"depreciacion_acumulada": monto_mensual},
                "$set": {"ultima_depreciacion": datetime.utcnow()},
            }
        )

    @staticmethod
    def listar_activos_activos(empresa_id: str) -> list:
        """Solo activos que aún tienen vida útil restante."""
        from pymongo import ASCENDING
        pipeline = [
            {"$match": {"empresa_id": empresa_id, "activo": True}},
            {"$addFields": {
                "valor_residual": {
                    "$subtract": ["$valor_historico", "$depreciacion_acumulada"]
                }
            }},
            {"$match": {"valor_residual": {"$gt": 0}}},
        ]
        return list(_col().aggregate(pipeline))
