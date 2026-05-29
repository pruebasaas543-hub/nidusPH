"""
app/servicios/boton_panico/model.py
Capa de datos para el módulo Botón de Pánico.

Colecciones MongoDB:
  panic_configurations – un documento por empresa  (nivel="empresa")
                         contiene mensajes, canales activos y contactos configurados
  panic_events         – historial de activaciones (quién disparó y resultado)
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _configs():  return db["panic_configurations"]
def _eventos():  return db["panic_events"]


class PanicConfigModel:

    @staticmethod
    def _q(empresa_id: str) -> dict:
        return {"empresa_id": ObjectId(empresa_id)}

    # ── Lectura completa ──────────────────────────────────────────────────

    @staticmethod
    def obtener(empresa_id: str) -> dict:
        return _configs().find_one(PanicConfigModel._q(empresa_id)) or {}

    # ── Mensajes y canales ────────────────────────────────────────────────

    @staticmethod
    def obtener_mensajes_empresa(empresa_id: str) -> dict:
        doc = PanicConfigModel.obtener(empresa_id)
        return {
            "mensaje_sms":      doc.get("mensaje_sms",      "").strip(),
            "mensaje_whatsapp": doc.get("mensaje_whatsapp", "").strip(),
            "mensaje_llamada":  doc.get("mensaje_llamada",  "").strip(),
            "activo_sms":       doc.get("activo_sms",       True),
            "activo_whatsapp":  doc.get("activo_whatsapp",  True),
            "activo_llamada":   doc.get("activo_llamada",   True),
            "cooldown_max":     doc.get("cooldown_max",     2),
            "cooldown_minutos": doc.get("cooldown_minutos", 10),
            "creado_en":        doc.get("creado_en"),
            "actualizado_en":   doc.get("actualizado_en"),
        }

    @staticmethod
    def guardar_mensaje_empresa(empresa_id: str, campo: str, texto: str):
        ahora = datetime.utcnow()
        _configs().update_one(
            PanicConfigModel._q(empresa_id),
            {
                "$set":         {campo: texto.strip(), "actualizado_en": ahora},
                "$setOnInsert": {"creado_en": ahora},
            },
            upsert=True,
        )

    @staticmethod
    def guardar_activo_canal(empresa_id: str, tipo: str, activo: bool):
        ahora = datetime.utcnow()
        # Pipeline de agregación: inicializa campos faltantes sin sobreescribir los existentes
        campos = {
            "activo_sms":      {"$ifNull": ["$activo_sms",      True]},
            "activo_whatsapp": {"$ifNull": ["$activo_whatsapp", True]},
            "activo_llamada":  {"$ifNull": ["$activo_llamada",  True]},
            f"activo_{tipo}":  activo,
            "actualizado_en":  ahora,
            "creado_en":       {"$ifNull": ["$creado_en", ahora]},
        }
        _configs().update_one(
            PanicConfigModel._q(empresa_id),
            [{"$set": campos}],
            upsert=True,
        )

    @staticmethod
    def limpiar_mensaje_empresa(empresa_id: str, campo: str):
        ahora = datetime.utcnow()
        _configs().update_one(
            PanicConfigModel._q(empresa_id),
            {
                "$set":         {campo: "", "actualizado_en": ahora},
                "$setOnInsert": {"creado_en": ahora},
            },
            upsert=True,
        )

    # ── Contactos ─────────────────────────────────────────────────────────

    @staticmethod
    def guardar_contactos(empresa_id: str,
                          contactos_externos: list,
                          contactos_directorio: list):
        ahora = datetime.utcnow()
        _configs().update_one(
            PanicConfigModel._q(empresa_id),
            {
                "$set": {
                    "contactos_externos":   contactos_externos,
                    "contactos_directorio": contactos_directorio,
                    "actualizado_en":       ahora,
                },
                "$setOnInsert": {"creado_en": ahora},
            },
            upsert=True,
        )

    @staticmethod
    def guardar_cooldown(empresa_id: str, cooldown_max: int, cooldown_minutos: int):
        ahora = datetime.utcnow()
        _configs().update_one(
            PanicConfigModel._q(empresa_id),
            {
                "$set": {
                    "cooldown_max":      cooldown_max,
                    "cooldown_minutos":  cooldown_minutos,
                    "actualizado_en":    ahora,
                },
                "$setOnInsert": {"creado_en": ahora},
            },
            upsert=True,
        )


class PanicEventModel:

    @staticmethod
    def registrar(empresa_id: str, residente_id: str, resultado: dict, ip: str = "",
                  nombre_residente: str = "", nombre_empresa: str = "") -> str:
        doc = {
            "empresa_id":       ObjectId(empresa_id),
            "residente_id":     residente_id,
            "nombre_residente": nombre_residente,
            "nombre_empresa":   nombre_empresa,
            "activado_en":      datetime.utcnow(),
            "resultado":        resultado,
            "ip":               ip,
        }
        return str(_eventos().insert_one(doc).inserted_id)

    @staticmethod
    def listar_por_empresa(empresa_id: str, limite: int = 10, filtro_fechas: dict = None):
        filtro = {"empresa_id": ObjectId(empresa_id)}
        if filtro_fechas:
            filtro["activado_en"] = filtro_fechas
        return list(
            _eventos()
            .find(filtro)
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

    @staticmethod
    def contar_recientes(empresa_id: str, residente_id: str, minutos: int) -> int:
        from datetime import timedelta
        desde = datetime.utcnow() - timedelta(minutes=minutos)
        return _eventos().count_documents({
            "empresa_id":   ObjectId(empresa_id),
            "residente_id": residente_id,
            "activado_en":  {"$gte": desde},
        })
