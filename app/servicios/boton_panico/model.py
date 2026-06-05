"""
app/servicios/boton_panico/model.py
Capa de datos para el módulo Botón de Pánico.

Colecciones MongoDB:
  panic_configurations      – un documento por empresa  (nivel="empresa")
                              contiene mensajes, canales activos
  user_panic_contacts       – contactos externos personales por usuario
                              cada documento = un contacto de un usuario en una empresa
  panic_events              – historial de activaciones (quién disparó y resultado)
"""

from app import db
from datetime import datetime
from bson import ObjectId


# Mapeo de estados Twilio → estados internos en español
MAPA_ESTADOS = {
    "queued":       "en_cola",
    "sending":      "enviando",
    "sent":         "recibido",
    "delivered":    "entregado",
    "undelivered":  "no_entregado",
    "read":         "leido",
    "initiated":    "en_cola",
    "ringing":      "sonando",
    "in-progress":  "en_llamada",
    "completed":    "completado",
    "no-answer":    "no_contesto",
    "busy":         "ocupado",
    "canceled":     "cancelado",
    "failed":       "fallido",
    "error":        "fallido",
    "mock":         "mock",
}

# Jerarquía ordenada de estados por canal (en español)
JERARQUIA_ESTADOS = {
    "sms": [
        "en_cola", "enviando", "recibido", "entregado",
        "no_entregado", "fallido"
    ],
    "whatsapp": [
        "en_cola", "enviando", "recibido", "entregado",
        "leido", "no_entregado", "fallido"
    ],
    "llamada": [
        "en_cola", "enviando", "sonando", "en_llamada",
        "completado", "ocupado", "no_contesto", "cancelado", "fallido"
    ],
}

ESTADOS_PENDIENTES = {
    "en_cola", "enviando", "sonando", "en_llamada", "recibido"
}
ESTADOS_FINALES = {
    "entregado", "leido", "completado",
    "no_entregado", "ocupado", "no_contesto", "cancelado", "fallido", "mock"
}


def _configs():      return db["panic_configurations"]
def _eventos():      return db["panic_events"]
def _user_contacts(): return db["user_panic_contacts"]
def _notification_states(): return db["notification_states"]
def _twilio_logs(): return db["twilio_requests_log"]


class NotificationStateModel:
    """Gestiona estados de notificaciones desde la BD (sin código quemado)."""

    @staticmethod
    def obtener_estado(tipo_notificacion: str, estado_twilio: str) -> dict:
        """Obtiene documento de estado desde BD basado en tipo y estado Twilio.

        Args:
            tipo_notificacion: "llamada", "sms", "whatsapp"
            estado_twilio: estado devuelto por Twilio (ej: "in-progress", "completed")

        Returns:
            dict con campos: estadoNotificacion, nombreEspanol, razonTerminacion, etc.
            {} si no encuentra
        """
        return _notification_states().find_one({
            "tipoNotificacion": tipo_notificacion,
            "estadoNotificacion": estado_twilio
        }) or {}

    @staticmethod
    def obtener_estados_por_tipo(tipo_notificacion: str) -> list:
        """Obtiene todos los estados posibles para un tipo de notificación.

        Returns:
            Lista ordenada de documentos de estado
        """
        return list(_notification_states().find({
            "tipoNotificacion": tipo_notificacion
        }).sort("orden", 1))

    @staticmethod
    def obtener_nombre_espanol(tipo_notificacion: str, estado_twilio: str) -> str:
        """Convierte estado Twilio a nombre en español.

        Ej: "in-progress" → "en_llamada"
        """
        doc = NotificationStateModel.obtener_estado(tipo_notificacion, estado_twilio)
        return doc.get("nombreEspanol", estado_twilio.lower())

    @staticmethod
    def es_estado_terminal(tipo_notificacion: str, estado_twilio: str) -> bool:
        """Verifica si un estado es terminal (final)."""
        doc = NotificationStateModel.obtener_estado(tipo_notificacion, estado_twilio)
        return doc.get("esTerminal", False)

    @staticmethod
    def es_estado_pendiente(tipo_notificacion: str, estado_español: str) -> bool:
        """Verifica si un estado es pendiente (aún puede cambiar).

        Args:
            tipo_notificacion: "llamada", "sms", "whatsapp"
            estado_español: nombre en español del estado (ej: "en_llamada")
        """
        # Buscar el estado por nombre español (para estados ya mapeados)
        doc = _notification_states().find_one({
            "tipoNotificacion": tipo_notificacion,
            "nombreEspanol": estado_español
        })
        if doc:
            return doc.get("esPendiente", False)
        return False

    @staticmethod
    def obtener_razon_terminacion(tipo_notificacion: str, estado_twilio: str) -> str:
        """Obtiene la razón por la que terminó (si aplica)."""
        doc = NotificationStateModel.obtener_estado(tipo_notificacion, estado_twilio)
        return doc.get("razonTerminacion", "")


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
                          contactos_directorio: list):
        ahora = datetime.utcnow()
        _configs().update_one(
            PanicConfigModel._q(empresa_id),
            {
                "$set": {
                    "contactos_directorio": contactos_directorio,
                    "actualizado_en":       ahora,
                },
                "$setOnInsert": {"creado_en": ahora},
                "$unset": {"contactos_externos": ""}
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


class TwilioRequestLogModel:
    """Registra trazas completas de peticiones a Twilio."""

    @staticmethod
    def registrar_peticion(evento_id: str, tipo_notificacion: str, contacto_nombre: str,
                          numero: str, peticion: dict, respuesta_inicial: dict,
                          usuario: str = "", empresa: str = "", activado_en: str = "") -> str:
        """Registra una petición y respuesta inicial de Twilio.

        Returns:
            ID del documento creado
        """
        from datetime import datetime
        doc = {
            "evento_id": ObjectId(evento_id) if evento_id else None,
            "usuario": usuario,
            "empresa": empresa,
            "activado_en": activado_en,
            "contacto_externo": {
                "nombre": contacto_nombre,
                "numero": numero
            },
            "tipo_notificacion": tipo_notificacion,
            "peticion_twilio": peticion,
            "respuesta_inicial": respuesta_inicial,
            "transiciones_estado": [],
            "errores": None,
            "guardado_en": datetime.utcnow().isoformat()
        }
        result = _twilio_logs().insert_one(doc)
        return str(result.inserted_id)

    @staticmethod
    def agregar_transicion(log_id: str, estado: str, timestamp: str, detalles: str = ""):
        """Agrega una transición de estado al log."""
        # Obtener el documento actual
        doc = _twilio_logs().find_one({"_id": ObjectId(log_id)})
        if not doc:
            return False

        transiciones = doc.get("transiciones_estado", [])
        transiciones.append({
            "orden": len(transiciones) + 1,
            "estado": estado,
            "timestamp": timestamp,
            "detalles": detalles
        })

        _twilio_logs().update_one(
            {"_id": ObjectId(log_id)},
            {"$set": {"transiciones_estado": transiciones}}
        )
        return True

    @staticmethod
    def registrar_error(log_id: str, error: str):
        """Registra un error en el log."""
        _twilio_logs().update_one(
            {"_id": ObjectId(log_id)},
            {"$set": {"errores": error}}
        )

    @staticmethod
    def obtener_traza(evento_id: str) -> list:
        """Obtiene todas las trazas de un evento específico."""
        return list(_twilio_logs().find({
            "evento_id": ObjectId(evento_id)
        }).sort("guardado_en", 1))

    @staticmethod
    def obtener_traza_por_id(log_id: str) -> dict:
        """Obtiene una traza específica por ID."""
        return _twilio_logs().find_one({"_id": ObjectId(log_id)}) or {}


class UserPanicContactModel:
    """Contactos externos personales por usuario (normalizado)."""

    @staticmethod
    def crear(usuario_id: str, empresa_id: str, nombre: str, telefono: str = None,
              descripcion: str = "", habilitado: bool = True, habilitado_para_sms: bool = False,
              habilitado_para_whatsapp: bool = False, habilitado_para_llamada: bool = False,
              prefijo: str = None, celular: str = None) -> tuple:
        """Crear contacto personal."""
        try:
            ahora = datetime.utcnow()
            # Si viene prefijo+celular, combinar en telefono; si viene telefono, mantener como está
            tel_completo = telefono or f"{prefijo or '+57'}{celular or ''}"
            doc = {
                "usuario_id":               ObjectId(usuario_id),
                "empresa_id":               ObjectId(empresa_id),
                "nombre":                   str(nombre).strip(),
                "prefijo":                  str(prefijo or '+57').strip(),
                "celular":                  str(celular or '').strip(),
                "telefono":                 str(tel_completo).strip(),
                "descripcion":              str(descripcion).strip(),
                "habilitado":               bool(habilitado),
                "habilitado_para_sms":      bool(habilitado_para_sms),
                "habilitado_para_whatsapp": bool(habilitado_para_whatsapp),
                "habilitado_para_llamada":  bool(habilitado_para_llamada),
                "creado_en":                ahora,
                "actualizado_en":           ahora,
            }
            result = _user_contacts().insert_one(doc)
            doc["_id"] = result.inserted_id
            return True, doc
        except Exception as e:
            return False, str(e)

    @staticmethod
    def listar(usuario_id: str, empresa_id: str) -> list:
        """Obtener contactos personales del usuario en una empresa."""
        return list(_user_contacts().find({
            "usuario_id": ObjectId(usuario_id),
            "empresa_id": ObjectId(empresa_id),
        }).sort("nombre", 1))

    @staticmethod
    def actualizar(contacto_id: str, datos: dict) -> tuple:
        """Actualizar contacto."""
        try:
            actualizables = {"nombre", "telefono", "descripcion", "habilitado",
                           "habilitado_para_sms", "habilitado_para_whatsapp", "habilitado_para_llamada",
                           "prefijo", "celular"}
            update_data = {k: v for k, v in datos.items() if k in actualizables}
            if not update_data:
                return False, "Sin cambios"
            # Si se actualiza prefijo o celular, regenerar telefono completo
            if "prefijo" in update_data or "celular" in update_data:
                contacto_actual = _user_contacts().find_one({"_id": ObjectId(contacto_id)}) or {}
                prefijo = update_data.get("prefijo", contacto_actual.get("prefijo", "+57"))
                celular = update_data.get("celular", contacto_actual.get("celular", ""))
                update_data["telefono"] = f"{prefijo}{celular}"
            update_data["actualizado_en"] = datetime.utcnow()
            result = _user_contacts().update_one(
                {"_id": ObjectId(contacto_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0, "Actualizado" if result.modified_count > 0 else "No encontrado"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def eliminar(contacto_id: str) -> tuple:
        """Eliminar contacto."""
        try:
            result = _user_contacts().delete_one({"_id": ObjectId(contacto_id)})
            return result.deleted_count > 0, "Eliminado" if result.deleted_count > 0 else "No encontrado"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def obtener(contacto_id: str) -> dict:
        """Obtener un contacto por ID."""
        return _user_contacts().find_one({"_id": ObjectId(contacto_id)}) or {}

    @staticmethod
    def migrar_desde_empresa(empresa_id: str, usuario_id: str = None) -> tuple:
        """Migrar contactos de panic_configurations a user_panic_contacts.
        Si usuario_id es None, los contactos migran como 'creados por sistema'."""
        try:
            cfg = _configs().find_one({"empresa_id": ObjectId(empresa_id)})
            if not cfg or not cfg.get("contactos_externos"):
                return True, 0

            creado_por = ObjectId(usuario_id) if usuario_id else None
            ahora = datetime.utcnow()
            count = 0

            for contacto in cfg.get("contactos_externos", []):
                # Evitar duplicados
                existe = _user_contacts().find_one({
                    "empresa_id": ObjectId(empresa_id),
                    "nombre": contacto.get("nombre"),
                    "telefono": contacto.get("telefono"),
                })
                if existe:
                    continue

                doc = {
                    "usuario_id":    creado_por,  # None para "sistema"
                    "empresa_id":    ObjectId(empresa_id),
                    "nombre":        contacto.get("nombre", ""),
                    "telefono":      contacto.get("telefono", ""),
                    "descripcion":   "Migrado de configuración empresa",
                    "habilitado":    True,
                    "creado_en":     ahora,
                    "actualizado_en": ahora,
                }
                _user_contacts().insert_one(doc)
                count += 1

            # Limpiar contactos_externos de panic_configurations
            _configs().update_one(
                {"empresa_id": ObjectId(empresa_id)},
                {"$unset": {"contactos_externos": ""}}
            )
            return True, count
        except Exception as e:
            return False, str(e)
