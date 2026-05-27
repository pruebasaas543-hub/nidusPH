"""
app/servicios/boton_panico/model.py
Capa de datos para el módulo Botón de Pánico.

Colecciones MongoDB:
  panic_configurations – configuración por residente/empresa
  panic_events         – historial de activaciones
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _configs():  return db["panic_configurations"]
def _eventos():  return db["panic_events"]


class PanicConfigModel:

    @staticmethod
    def obtener(empresa_id: str, residente_id: str):
        return _configs().find_one({
            "empresa_id":   ObjectId(empresa_id),
            "residente_id": residente_id,
        })

    @staticmethod
    def guardar(empresa_id: str, residente_id: str,
                contactos_externos: list, contactos_directorio: list):
        ahora = datetime.utcnow()
        _configs().update_one(
            {"empresa_id": ObjectId(empresa_id), "residente_id": residente_id},
            {
                "$set": {
                    "contactos_externos":    contactos_externos,
                    "contactos_directorio":  contactos_directorio,
                    "actualizado_en":        ahora,
                },
                "$setOnInsert": {"creado_en": ahora},
            },
            upsert=True,
        )


class PanicEventModel:

    @staticmethod
    def registrar(empresa_id: str, residente_id: str, resultado: dict, ip: str = "") -> str:
        doc = {
            "empresa_id":   ObjectId(empresa_id),
            "residente_id": residente_id,
            "activado_en":  datetime.utcnow(),
            "resultado":    resultado,
            "ip":           ip,
        }
        return str(_eventos().insert_one(doc).inserted_id)

    @staticmethod
    def listar_por_empresa(empresa_id: str, limite: int = 10):
        return list(
            _eventos()
            .find({"empresa_id": ObjectId(empresa_id)})
            .sort("activado_en", -1)
            .limit(limite)
        )

    @staticmethod
    def listar_por_residente(empresa_id: str, residente_id: str, limite: int = 5):
        return list(
            _eventos()
            .find({"empresa_id": ObjectId(empresa_id), "residente_id": residente_id})
            .sort("activado_en", -1)
            .limit(limite)
        )
