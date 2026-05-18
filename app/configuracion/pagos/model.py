"""
app/configuracion/pagos/model.py
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col(): return db["asociacion_datos_pago"]


class AsociacionDatosPagoModel:

    @staticmethod
    def crear(empresa_id: str, tipo: str, datos: dict, creado_por: str) -> str:
        doc = {
            "empresa_id":     ObjectId(empresa_id),
            "tipo":           tipo,
            "habilitado":     datos.get("habilitado", True),
            "datos":          datos.get("datos", {}),
            "creado_en":      datetime.utcnow(),
            "creado_por":     creado_por,
            "actualizado_en": None,
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def actualizar(config_id: str, datos: dict):
        _col().update_one(
            {"_id": ObjectId(config_id)},
            {"$set": {
                "habilitado":     datos.get("habilitado", True),
                "datos":          datos.get("datos", {}),
                "actualizado_en": datetime.utcnow(),
            }}
        )

    @staticmethod
    def obtener(config_id: str):
        return _col().find_one({"_id": ObjectId(config_id)})

    @staticmethod
    def listar_por_empresa(empresa_id: str) -> list:
        return list(_col().find({"empresa_id": ObjectId(empresa_id)}).sort("tipo", 1))

    @staticmethod
    def listar_por_tipo(empresa_id: str, tipo: str) -> list:
        return list(_col().find({"empresa_id": ObjectId(empresa_id), "tipo": tipo}).sort("creado_en", 1))

    @staticmethod
    def eliminar(config_id: str):
        _col().delete_one({"_id": ObjectId(config_id)})
