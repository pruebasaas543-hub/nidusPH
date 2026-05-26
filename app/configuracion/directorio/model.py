"""
app/configuracion/directorio/model.py
Colección: directorio
Directorio de contactos de la propiedad horizontal.
"""

import base64
from app import db
from datetime import datetime
from bson import ObjectId

BLOQUES = ["EMERGENCIAS", "ADMIN", "PUBLICOS", "LOGISTICA", "LOCAL"]

MAX_FOTO_BYTES  = 2 * 1024 * 1024   # 2 MB
FOTO_MIME_OK    = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _col():
    return db["directorio"]


def _foto_a_doc(file_storage):
    """Convierte un FileStorage a {data, mimetype} o None si no hay archivo."""
    if not file_storage or not file_storage.filename:
        return None
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_FOTO_BYTES:
        raise ValueError("La foto supera el límite de 2 MB")
    mimetype = file_storage.mimetype or "image/jpeg"
    if mimetype not in FOTO_MIME_OK:
        raise ValueError("Formato de imagen no permitido (JPG, PNG, WEBP, GIF)")
    raw = file_storage.read()
    return {
        "data":     base64.b64encode(raw).decode("utf-8"),
        "mimetype": mimetype,
    }


class DirectorioModel:

    @staticmethod
    def listar(propiedad_id: str, bloque: str = None) -> list:
        filtro = {"propiedad_id": ObjectId(propiedad_id), "activo": True}
        if bloque and bloque in BLOQUES:
            filtro["bloque"] = bloque
        docs = list(_col().find(filtro).sort([("bloque", 1), ("nombre", 1)]))
        resultado = []
        for d in docs:
            resultado.append({
                "_id":                          str(d["_id"]),
                "propiedad_id":                 str(d["propiedad_id"]),
                "bloque":                       d.get("bloque", ""),
                "nombre":                       d.get("nombre", ""),
                "telefonos":                    d.get("telefonos", []),
                "correo":                       d.get("correo", ""),
                "tiene_foto":                   bool(d.get("foto_data")),
                "nota_referencia":              d.get("nota_referencia", ""),
                "es_visible_para_residentes":   d.get("es_visible_para_residentes", True),
                "requiere_autenticacion":       d.get("requiere_autenticacion", False),
                "permite_llamada_rapida":       d.get("permite_llamada_rapida", False),
                "vinculado_al_boton_de_panico": d.get("vinculado_al_boton_de_panico", False),
                "creado_en":                    d.get("creado_en"),
            })
        return resultado

    @staticmethod
    def obtener(contacto_id: str):
        try:
            return _col().find_one({"_id": ObjectId(contacto_id)})
        except Exception:
            return None

    @staticmethod
    def crear(propiedad_id: str, datos: dict, archivo, creado_por: str) -> str:
        foto = _foto_a_doc(archivo)
        telefonos = [t.strip() for t in datos.get("telefonos", []) if t.strip()]
        doc = {
            "propiedad_id":                 ObjectId(propiedad_id),
            "bloque":                       datos["bloque"].strip().upper(),
            "nombre":                       datos["nombre"].strip(),
            "telefonos":                    telefonos,
            "correo":                       datos.get("correo", "").strip().lower(),
            "foto_data":                    foto["data"]     if foto else None,
            "foto_mimetype":                foto["mimetype"] if foto else None,
            "nota_referencia":              datos.get("nota_referencia", "").strip(),
            "es_visible_para_residentes":   bool(datos.get("es_visible_para_residentes", True)),
            "requiere_autenticacion":       bool(datos.get("requiere_autenticacion", False)),
            "permite_llamada_rapida":       bool(datos.get("permite_llamada_rapida", False)),
            "vinculado_al_boton_de_panico": bool(datos.get("vinculado_al_boton_de_panico", False)),
            "activo":                       True,
            "creado_en":                    datetime.utcnow(),
            "creado_por":                   creado_por,
            "actualizado_en":               None,
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def actualizar(contacto_id: str, datos: dict, archivo):
        foto = _foto_a_doc(archivo)
        telefonos = [t.strip() for t in datos.get("telefonos", []) if t.strip()]
        update = {
            "bloque":                       datos["bloque"].strip().upper(),
            "nombre":                       datos["nombre"].strip(),
            "telefonos":                    telefonos,
            "correo":                       datos.get("correo", "").strip().lower(),
            "nota_referencia":              datos.get("nota_referencia", "").strip(),
            "es_visible_para_residentes":   bool(datos.get("es_visible_para_residentes", True)),
            "requiere_autenticacion":       bool(datos.get("requiere_autenticacion", False)),
            "permite_llamada_rapida":       bool(datos.get("permite_llamada_rapida", False)),
            "vinculado_al_boton_de_panico": bool(datos.get("vinculado_al_boton_de_panico", False)),
            "actualizado_en":               datetime.utcnow(),
        }
        if foto:
            update["foto_data"]     = foto["data"]
            update["foto_mimetype"] = foto["mimetype"]
        _col().update_one({"_id": ObjectId(contacto_id)}, {"$set": update})

    @staticmethod
    def eliminar(contacto_id: str):
        _col().update_one(
            {"_id": ObjectId(contacto_id)},
            {"$set": {"activo": False, "actualizado_en": datetime.utcnow()}}
        )

    @staticmethod
    def obtener_foto(contacto_id: str):
        try:
            doc = _col().find_one(
                {"_id": ObjectId(contacto_id)},
                {"foto_data": 1, "foto_mimetype": 1}
            )
            if not doc or not doc.get("foto_data"):
                return None
            return {"data": doc["foto_data"], "mimetype": doc.get("foto_mimetype", "image/jpeg")}
        except Exception:
            return None
