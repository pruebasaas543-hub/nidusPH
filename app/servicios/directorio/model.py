"""
app/servicios/directorio/model.py
Capa de datos para el módulo Directorio de Contactos.

Colección MongoDB:
  directorio_contactos – contactos de emergencia, admin, públicos, logística y locales
"""

import base64
from app import db
from datetime import datetime
from bson import ObjectId


BLOQUES_VALIDOS = {"EMERGENCIAS", "ADMIN", "PUBLICOS", "LOGISTICA", "LOCAL"}


def _contactos(): return db["directorio_contactos"]


class ContactoModel:

    @staticmethod
    def crear(datos: dict, empresa_id: str, creado_por: str) -> str:
        doc = {
            "empresa_id":                   ObjectId(empresa_id),
            "bloque":                       datos["bloque"].upper(),
            "nombre":                       datos["nombre"].strip(),
            "cargo_titulo":                 datos.get("cargo_titulo", "").strip(),
            "telefonos":                    datos.get("telefonos", []),
            "correo":                       datos.get("correo", "").strip().lower(),
            "foto_data":                    datos.get("foto_data"),
            "foto_mimetype":                datos.get("foto_mimetype"),
            "nota_referencia":              datos.get("nota_referencia", "").strip(),
            "es_visible_para_residentes":   bool(datos.get("es_visible_para_residentes", True)),
            "es_visible_para_seguridad":       bool(datos.get("es_visible_para_seguridad", False)),
            "es_visible_para_administracion":       bool(datos.get("es_visible_para_administracion", False)),
            "vinculado_al_boton_de_panico": bool(datos.get("vinculado_al_boton_de_panico", False)),
            "orden":                        int(datos.get("orden", 0)),
            "activo":                       True,
            "creado_en":                    datetime.utcnow(),
            "creado_por":                   creado_por,
            "actualizado_en":               None,
        }
        return str(_contactos().insert_one(doc).inserted_id)

    @staticmethod
    def listar_por_empresa(empresa_id: str, solo_activos: bool = True) -> list:
        filtro = {"empresa_id": ObjectId(empresa_id)}
        if solo_activos:
            filtro["activo"] = True
        return list(_contactos().find(filtro).sort([("bloque", 1), ("orden", 1), ("nombre", 1)]))

    @staticmethod
    def obtener(contacto_id: str, empresa_id: str = None):
        try:
            filtro = {"_id": ObjectId(contacto_id)}
            if empresa_id:
                filtro["empresa_id"] = ObjectId(empresa_id)
            return _contactos().find_one(filtro)
        except Exception:
            return None

    @staticmethod
    def actualizar(contacto_id: str, empresa_id: str, datos: dict):
        sets = {
            "bloque":                       datos["bloque"].upper(),
            "nombre":                       datos["nombre"].strip(),
            "cargo_titulo":                 datos.get("cargo_titulo", "").strip(),
            "telefonos":                    datos.get("telefonos", []),
            "correo":                       datos.get("correo", "").strip().lower(),
            "nota_referencia":              datos.get("nota_referencia", "").strip(),
            "es_visible_para_residentes":   bool(datos.get("es_visible_para_residentes", True)),
            "es_visible_para_seguridad":       bool(datos.get("es_visible_para_seguridad", False)),
            "es_visible_para_administracion":       bool(datos.get("es_visible_para_administracion", False)),
            "vinculado_al_boton_de_panico": bool(datos.get("vinculado_al_boton_de_panico", False)),
            "orden":                        int(datos.get("orden", 0)),
            "activo":                       bool(datos.get("activo", True)),
            "actualizado_en":               datetime.utcnow(),
        }
        if datos.get("foto_data") is not None:
            sets["foto_data"]     = datos["foto_data"]
            sets["foto_mimetype"] = datos.get("foto_mimetype", "image/jpeg")
        _contactos().update_one(
            {"_id": ObjectId(contacto_id), "empresa_id": ObjectId(empresa_id)},
            {"$set": sets}
        )

    @staticmethod
    def eliminar(contacto_id: str, empresa_id: str):
        try:
            _contactos().delete_one(
                {"_id": ObjectId(contacto_id), "empresa_id": ObjectId(empresa_id)}
            )
        except Exception:
            pass
