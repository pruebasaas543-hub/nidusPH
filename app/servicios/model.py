"""
app/servicios/model.py
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col(): return db["servicios"]


class ServicioModel:

    @staticmethod
    def crear(datos: dict, creado_por: str) -> str:
        nombre = datos.get("nombre", "").strip()
        codigo = nombre.lower().replace(" ", "_").replace("-", "_")
        doc = {
            "nombre":      nombre,
            "codigo":      datos.get("codigo", codigo).strip().lower().replace(" ", "_"),
            "descripcion": datos.get("descripcion", "").strip(),
            "icono":       datos.get("icono", "📋").strip(),
            "orden":       int(datos.get("orden", 99) or 99),
            "activo":      True,
            "creado_en":   datetime.utcnow(),
            "creado_por":  creado_por,
            "actualizado_en": None,
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def listar(solo_activos: bool = False) -> list:
        filtro = {"activo": True} if solo_activos else {}
        return list(_col().find(filtro).sort("orden", 1))

    @staticmethod
    def obtener(servicio_id: str):
        return _col().find_one({"_id": ObjectId(servicio_id)})

    @staticmethod
    def actualizar(servicio_id: str, datos: dict):
        update = {
            "nombre":         datos.get("nombre", "").strip(),
            "descripcion":    datos.get("descripcion", "").strip(),
            "icono":          datos.get("icono", "📋").strip(),
            "orden":          int(datos.get("orden", 99) or 99),
            "actualizado_en": datetime.utcnow(),
        }
        if datos.get("codigo"):
            update["codigo"] = datos["codigo"].strip().lower().replace(" ", "_")
        _col().update_one({"_id": ObjectId(servicio_id)}, {"$set": update})

    @staticmethod
    def cambiar_estado(servicio_id: str, activo: bool):
        _col().update_one(
            {"_id": ObjectId(servicio_id)},
            {"$set": {"activo": activo, "actualizado_en": datetime.utcnow()}}
        )

    @staticmethod
    def eliminar(servicio_id: str):
        _col().delete_one({"_id": ObjectId(servicio_id)})

    @staticmethod
    def buscar_por_codigo(codigo: str):
        return _col().find_one({"codigo": codigo.strip().lower()})
