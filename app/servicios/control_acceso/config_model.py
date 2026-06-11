"""
app/servicios/control_acceso/config_model.py
────────────────────────────────────────────
Modelos para la configuración global de Control de Acceso por empresa.

Colecciones NUEVAS:
  - controlAcceso_config    : configuración por conjunto (una por empresa)
  - controlAcceso_blacklist : personas bloqueadas por conjunto
"""

from datetime import datetime
from bson import ObjectId
from app import db


def _cfg():       return db["controlAcceso_config"]
def _blacklist(): return db["controlAcceso_blacklist"]


# ── Configuración por empresa ──────────────────────────────────────────────

class CaConfigModel:

    DEFAULTS = {
        "autenticacion": {
            "qr_activo":           True,
            "pin_activo":          True,
            "cronometro_minutos":  120,
        },
        "segmentacion": {
            "peatonal":   True,
            "vehicular":  True,
            "tipos_visita": ["visita", "contratista", "domicilio"],
        },
        "puntos_acceso": [
            {"id": "principal", "nombre": "Portería Principal", "activo": True}
        ],
        "lockdown": {
            "activo":              False,
            "activado_por":        None,
            "activado_en":         None,
            "notificar_whatsapp":  True,
            "notificar_llamada":   True,
            "numeros_emergencia":  [],
        },
        "flujo_contratistas": {
            "requiere_aprobacion":   True,
            "sla_horas":             24,
            "alerta_porcentaje":     75,
            "documentos_requeridos": ["ARL", "EPS"],
        },
        "courier": {
            "timeout_minutos": 5,
        },
        "citofonia": {
            "activo":               True,
            "limite_llamadas_mes":  50,
        },
        "notificaciones": {
            "avisar_residente_ingreso": True,
        },
        "formularios": {
            "visita": [
                {"id": "f_nombre",    "label": "Nombre completo",  "tipo": "texto",   "requerido": True},
                {"id": "f_documento", "label": "N° Documento",     "tipo": "numero",  "requerido": True},
                {"id": "f_motivo",    "label": "Motivo de visita", "tipo": "texto",   "requerido": False},
            ],
            "contratista": [
                {"id": "f_nombre",   "label": "Nombre completo", "tipo": "texto",  "requerido": True},
                {"id": "f_doc",      "label": "N° Documento",    "tipo": "numero", "requerido": True},
                {"id": "f_empresa",  "label": "Empresa",         "tipo": "texto",  "requerido": True},
                {"id": "f_trabajo",  "label": "Trabajo a realizar", "tipo": "texto", "requerido": False},
            ],
            "domicilio": [
                {"id": "f_empresa",  "label": "Empresa / App",   "tipo": "texto",  "requerido": True},
                {"id": "f_nombre",   "label": "Nombre mensajero","tipo": "texto",  "requerido": False},
                {"id": "f_unidad",   "label": "Unidad destino",  "tipo": "texto",  "requerido": True},
            ],
            "proveedor": [
                {"id": "f_nombre",   "label": "Nombre completo", "tipo": "texto",  "requerido": True},
                {"id": "f_doc",      "label": "N° Documento",    "tipo": "numero", "requerido": True},
                {"id": "f_empresa",  "label": "Empresa",         "tipo": "texto",  "requerido": True},
            ],
        },
    }

    @staticmethod
    def obtener(empresa_id: str) -> dict:
        """Devuelve la config del conjunto. Si no existe, retorna los defaults."""
        doc = _cfg().find_one({"empresa_id": ObjectId(empresa_id)})
        if not doc:
            return {**CaConfigModel.DEFAULTS, "empresa_id": empresa_id, "_nueva": True}
        return doc

    @staticmethod
    def guardar(empresa_id: str, datos: dict) -> bool:
        """Upsert completo de la configuración del conjunto."""
        datos.pop("_id", None)
        datos.pop("_nueva", None)
        datos["empresa_id"]    = ObjectId(empresa_id)
        datos["actualizado_en"] = datetime.utcnow()
        r = _cfg().update_one(
            {"empresa_id": ObjectId(empresa_id)},
            {"$set": datos, "$setOnInsert": {"creado_en": datetime.utcnow()}},
            upsert=True,
        )
        return r.modified_count > 0 or r.upserted_id is not None

    @staticmethod
    def lockdown_activo(empresa_id: str) -> bool:
        """Verifica rápido si el conjunto está en lockdown."""
        doc = _cfg().find_one(
            {"empresa_id": ObjectId(empresa_id)},
            {"lockdown.activo": 1}
        )
        return bool((doc or {}).get("lockdown", {}).get("activo", False))

    @staticmethod
    def activar_lockdown(empresa_id: str, user_id: str, activar: bool) -> bool:
        upd = {
            "lockdown.activo":      activar,
            "lockdown.activado_por": ObjectId(user_id) if user_id else None,
            "lockdown.activado_en":  datetime.utcnow() if activar else None,
            "actualizado_en":        datetime.utcnow(),
        }
        r = _cfg().update_one(
            {"empresa_id": ObjectId(empresa_id)},
            {"$set": upd},
            upsert=True,
        )
        return r.modified_count > 0 or r.upserted_id is not None

    @staticmethod
    def get_puntos_acceso(empresa_id: str) -> list:
        doc = _cfg().find_one({"empresa_id": ObjectId(empresa_id)}, {"puntos_acceso": 1})
        return (doc or {}).get("puntos_acceso", CaConfigModel.DEFAULTS["puntos_acceso"])


# ── Lista negra ────────────────────────────────────────────────────────────

class CaBlacklistModel:

    @staticmethod
    def agregar(empresa_id: str, documento: str, nombre: str,
                motivo: str = "", bloqueado_por: str = "") -> str:
        doc = {
            "empresa_id":    ObjectId(empresa_id),
            "documento":     documento.strip(),
            "nombre":        nombre.strip(),
            "motivo":        motivo.strip(),
            "bloqueado_por": ObjectId(bloqueado_por) if bloqueado_por else None,
            "activo":        True,
            "creado_en":     datetime.utcnow(),
        }
        return str(_blacklist().insert_one(doc).inserted_id)

    @staticmethod
    def esta_bloqueado(empresa_id: str, documento: str) -> bool:
        return _blacklist().find_one({
            "empresa_id": ObjectId(empresa_id),
            "documento":  documento.strip(),
            "activo":     True,
        }) is not None

    @staticmethod
    def listar(empresa_id: str) -> list:
        return list(_blacklist().find(
            {"empresa_id": ObjectId(empresa_id), "activo": True}
        ).sort("creado_en", -1))

    @staticmethod
    def desactivar(blacklist_id: str) -> bool:
        r = _blacklist().update_one(
            {"_id": ObjectId(blacklist_id)},
            {"$set": {"activo": False, "desactivado_en": datetime.utcnow()}}
        )
        return r.modified_count > 0
