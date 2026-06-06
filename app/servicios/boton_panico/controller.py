"""
app/servicios/boton_panico/controller.py
Lógica de negocio para el módulo Botón de Pánico.
"""

import os
import logging
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape
from bson import ObjectId

from app import db
from app.servicios.boton_panico.model import (
    PanicConfigModel, PanicEventModel, NotificationStateModel, MAPA_ESTADOS
)

log = logging.getLogger(__name__)

TWILIO_FROM               = os.environ.get("TWILIO_PHONE_NUMBER", "")
TWILIO_WA_FROM            = os.environ.get("TWILIO_WHATSAPP_FROM", "")
TWILIO_PANIC_TEMPLATE_SID = os.environ.get("TWILIO_PANIC_TEMPLATE_SID", "")
TWILIO_WEBHOOK_URL        = os.environ.get("TWILIO_WEBHOOK_URL", "http://localhost:5000/servicios/boton_panico/webhook/twilio-status")

MSG_DEFAULT_SMS = (
    "EMERGENCIA: {nombre_residente} activo el boton de panico en "
    "{nombre_empresa}. Comuniquese de inmediato."
)
MSG_DEFAULT_WHATSAPP = (
    "🚨 EMERGENCIA: {nombre_residente} ha activado el botón de pánico "
    "en {nombre_empresa}. Comuníquese de inmediato."
)
MSG_DEFAULT_LLAMADA = (
    "Atencion. Se ha activado una alerta de emergencia. "
    "{nombre_residente} ha presionado el boton de panico "
    "en {nombre_empresa}. "
    "Por favor comuniquese de inmediato. "
    "Repito. Se ha activado una alerta de emergencia en {nombre_empresa}."
)


def _aplicar_vars(texto: str, nombre_residente: str, nombre_empresa: str,
                  torre: str = "", apartamento: str = "") -> str:
    return (texto
            .replace("{nombre_residente}", nombre_residente)
            .replace("{nombre_empresa}",   nombre_empresa)
            .replace("{torre}",            torre or "")
            .replace("{apartamento}",      apartamento or ""))


def _resultado_duplicado(numero: str, canal: str) -> dict:
    """Resultado controlado cuando un número ya fue notificado por ese canal en
    este mismo evento. Evita enviar 2 veces al mismo número: el segundo queda
    "fallido" con la causa clara (no se envía a Twilio)."""
    canal_txt = {"sms": "SMS", "whatsapp": "WhatsApp", "llamada": "llamada"}.get(canal, canal)
    detalle = f"Número duplicado: ya fue notificado por {canal_txt} en otro contacto"
    return {"numero": numero, "estado": "fallido", "detalle": detalle,
            "historial": [{"estado": "fallido", "en": _ts(), "detalle": detalle}]}


def _twilio_client():
    try:
        from twilio.rest import Client
        sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        if sid and token:
            return Client(sid, token)
    except ImportError:
        log.warning("twilio no instalado — envíos en modo mock")
    return None


def _construir_twiml(texto: str) -> str:
    try:
        from twilio.twiml.voice_response import VoiceResponse
        r = VoiceResponse()
        r.say(texto, voice="Polly.Lupe", language="es-US")
        r.pause(length=1)
        r.say(texto, voice="Polly.Lupe", language="es-US")
        r.hangup()
        twiml = str(r)
        log.info("TwiML generado: %s", twiml)
        return twiml
    except ImportError:
        texto_xml = xml_escape(texto)
        twiml = (
            '<Response>'
            f'<Say voice="Polly.Lupe" language="es-US">{texto_xml}</Say>'
            f'<Pause length="1"/>'
            f'<Say voice="Polly.Lupe" language="es-US">{texto_xml}</Say>'
            f'<Hangup/></Response>'
        )
        log.info("TwiML generado (fallback): %s", twiml)
        return twiml


def _numero_completo(prefijo: str, numero: str) -> str:
    p = (prefijo or "+57").strip()
    n = "".join(c for c in (numero or "") if c.isdigit())
    return f"{p}{n}"


def _telefonos_contacto(contacto_id: str) -> list:
    try:
        doc = db["directorio_contactos"].find_one(
            {"_id": ObjectId(contacto_id), "activo": True},
            {"telefonos": 1},
        )
        return doc.get("telefonos", []) if doc else []
    except Exception:
        return []


def _ts() -> str:
    return datetime.utcnow().isoformat()


def _enviar_sms(cliente, numero: str, mensaje: str, contacto_nombre: str = "", evento_id: str = "",
                usuario: str = "", empresa: str = "", activado_en: str = "") -> dict:
    if not cliente or not TWILIO_FROM:
        log.info("[MOCK] SMS → %s", numero)
        return {"numero": numero, "estado": "mock", "detalle": "Sin credenciales Twilio",
                "historial": [{"estado": "mock", "en": _ts()}]}
    try:
        msg = cliente.messages.create(
            to=numero, from_=TWILIO_FROM, body=mensaje,
            status_callback=TWILIO_WEBHOOK_URL
        )
        log.info("SMS enviado → %s (SID=%s)", numero, msg.sid)
        estado_raw = msg.status or "queued"
        # Obtener estado desde BD en lugar de mapeo hardcodeado
        estado_ini = NotificationStateModel.obtener_nombre_espanol("sms", estado_raw.lower())
        razon = NotificationStateModel.obtener_razon_terminacion("sms", estado_raw.lower())

        # Registrar en Twilio log
        if evento_id:
            from app.servicios.boton_panico.model import TwilioRequestLogModel
            log_id = TwilioRequestLogModel.registrar_peticion(
                evento_id, "sms", contacto_nombre, numero,
                {"to": numero, "from": TWILIO_FROM, "body": mensaje},
                {"sid": msg.sid, "status": estado_raw, "timestamp": _ts()},
                usuario, empresa, activado_en
            )
            TwilioRequestLogModel.agregar_transicion(log_id, estado_ini, _ts(), razon or "")

        return {"numero": numero, "estado": estado_ini, "sid": msg.sid,
                "historial": [{"estado": estado_ini, "en": _ts(), "razon": razon if razon else None}]}
    except Exception as e:
        log.error("SMS error → %s: %s", numero, e)
        if evento_id:
            from app.servicios.boton_panico.model import TwilioRequestLogModel
            log_id = TwilioRequestLogModel.registrar_peticion(
                evento_id, "sms", contacto_nombre, numero,
                {"to": numero, "from": TWILIO_FROM, "body": mensaje},
                {"error": str(e)},
                usuario, empresa, activado_en
            )
            TwilioRequestLogModel.registrar_error(log_id, str(e))
        return {"numero": numero, "estado": "fallido", "detalle": str(e),
                "historial": [{"estado": "fallido", "en": _ts(), "detalle": str(e)}]}


def _enviar_llamada(cliente, numero: str, twiml: str, contacto_nombre: str = "", evento_id: str = "",
                    usuario: str = "", empresa: str = "", activado_en: str = "") -> dict:
    if not cliente or not TWILIO_FROM:
        log.info("[MOCK] CALL → %s", numero)
        return {"numero": numero, "estado": "mock", "detalle": "Sin credenciales Twilio",
                "historial": [{"estado": "mock", "en": _ts()}]}
    try:
        call = cliente.calls.create(
            to=numero, from_=TWILIO_FROM, twiml=twiml,
            status_callback=TWILIO_WEBHOOK_URL,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            # Corta el timbre a los 18s para reportar "no-answer" (No Contestó)
            # ANTES de que entre el buzón (~25-30s). Ajustable según el operador.
            timeout=18,
            # AMD: detecta si contesta una persona o un buzón. Con timeout=18,
            # si el buzón alcanza a contestar es porque la línea estaba ocupada/
            # no disponible (desvío temprano) → lo marcamos "Ocupado".
            machine_detection="Enable",
        )
        log.info("Llamada iniciada → %s (SID=%s)", numero, call.sid)
        estado_raw = call.status or "queued"
        # Obtener estado desde BD en lugar de mapeo hardcodeado
        estado_ini = NotificationStateModel.obtener_nombre_espanol("llamada", estado_raw.lower())
        razon = NotificationStateModel.obtener_razon_terminacion("llamada", estado_raw.lower())

        # Registrar en Twilio log
        if evento_id:
            from app.servicios.boton_panico.model import TwilioRequestLogModel
            log_id = TwilioRequestLogModel.registrar_peticion(
                evento_id, "llamada", contacto_nombre, numero,
                {"to": numero, "from": TWILIO_FROM},
                {"sid": call.sid, "status": estado_raw, "timestamp": _ts()},
                usuario, empresa, activado_en
            )
            TwilioRequestLogModel.agregar_transicion(log_id, estado_ini, _ts(), razon or "")

        return {"numero": numero, "estado": estado_ini, "sid": call.sid,
                "historial": [{"estado": estado_ini, "en": _ts(), "razon": razon if razon else None}]}
    except Exception as e:
        log.error("Call error → %s: %s", numero, e)
        if evento_id:
            from app.servicios.boton_panico.model import TwilioRequestLogModel
            log_id = TwilioRequestLogModel.registrar_peticion(
                evento_id, "llamada", contacto_nombre, numero,
                {"to": numero, "from": TWILIO_FROM},
                {"error": str(e)},
                usuario, empresa, activado_en
            )
            TwilioRequestLogModel.registrar_error(log_id, str(e))
        return {"numero": numero, "estado": "fallido", "detalle": str(e),
                "historial": [{"estado": "fallido", "en": _ts(), "detalle": str(e)}]}


def _enviar_whatsapp(cliente, numero: str, cuerpo: str, contacto_nombre: str = "", evento_id: str = "",
                     usuario: str = "", empresa: str = "", activado_en: str = "") -> dict:
    if not cliente or not TWILIO_WA_FROM:
        log.info("[MOCK] WhatsApp → %s", numero)
        return {"numero": numero, "estado": "mock", "detalle": "Sin credenciales Twilio",
                "historial": [{"estado": "mock", "en": _ts()}]}
    try:
        kwargs = {"to": f"whatsapp:{numero}", "from_": TWILIO_WA_FROM, "status_callback": TWILIO_WEBHOOK_URL}
        if TWILIO_PANIC_TEMPLATE_SID:
            kwargs["content_sid"]       = TWILIO_PANIC_TEMPLATE_SID
            kwargs["content_variables"] = f'{{"1":"{cuerpo}"}}'
        else:
            kwargs["body"] = cuerpo
        msg = cliente.messages.create(**kwargs)
        log.info("WhatsApp enviado → %s (SID=%s)", numero, msg.sid)
        estado_raw = msg.status or "queued"
        # Obtener estado desde BD en lugar de mapeo hardcodeado
        estado_ini = NotificationStateModel.obtener_nombre_espanol("whatsapp", estado_raw.lower())
        razon = NotificationStateModel.obtener_razon_terminacion("whatsapp", estado_raw.lower())

        # Registrar en Twilio log
        if evento_id:
            from app.servicios.boton_panico.model import TwilioRequestLogModel
            log_id = TwilioRequestLogModel.registrar_peticion(
                evento_id, "whatsapp", contacto_nombre, numero,
                {"to": f"whatsapp:{numero}", "from": TWILIO_WA_FROM, "body": cuerpo},
                {"sid": msg.sid, "status": estado_raw, "timestamp": _ts()},
                usuario, empresa, activado_en
            )
            TwilioRequestLogModel.agregar_transicion(log_id, estado_ini, _ts(), razon or "")

        return {"numero": numero, "estado": estado_ini, "sid": msg.sid,
                "historial": [{"estado": estado_ini, "en": _ts(), "razon": razon if razon else None}]}
    except Exception as e:
        log.error("WhatsApp error → %s: %s", numero, e)
        if evento_id:
            from app.servicios.boton_panico.model import TwilioRequestLogModel
            log_id = TwilioRequestLogModel.registrar_peticion(
                evento_id, "whatsapp", contacto_nombre, numero,
                {"to": f"whatsapp:{numero}", "from": TWILIO_WA_FROM},
                {"error": str(e)},
                usuario, empresa, activado_en
            )
            TwilioRequestLogModel.registrar_error(log_id, str(e))
        return {"numero": numero, "estado": "fallido", "detalle": str(e),
                "historial": [{"estado": "fallido", "en": _ts(), "detalle": str(e)}]}


class PanicController:

    @staticmethod
    def obtener_config(empresa_id: str):
        cfg = PanicConfigModel.obtener(empresa_id)
        return True, cfg or {"contactos_directorio": []}

    @staticmethod
    def guardar_config(empresa_id: str, datos: dict):
        directorio = [
            {
                "contacto_id":              str(c.get("contacto_id", "")),
                "nombre":                   str(c.get("nombre", "")),
                "habilitado_para_sms":      bool(c.get("habilitado_para_sms", False)),
                "habilitado_para_llamar":   bool(c.get("habilitado_para_llamar", False)),
                "habilitado_para_whatsapp": bool(c.get("habilitado_para_whatsapp", False)),
            }
            for c in datos.get("contactos_directorio", [])
        ]

        PanicConfigModel.guardar_contactos(empresa_id, directorio)
        return True, "Configuración guardada"

    @staticmethod
    def trigger(empresa_id: str, residente_id: str,
                nombre_residente: str, nombre_empresa: str, ip: str = "",
                torre: str = "", apartamento: str = ""):

        cfg = PanicConfigModel.obtener(empresa_id)
        if not cfg or not cfg.get("contactos_directorio"):
            return False, "Sin configuración de pánico. Configura los contactos del directorio primero."

        # Cooldown: límite de activaciones por usuario dentro de una ventana de tiempo
        cooldown_max = int(cfg.get("cooldown_max", 2))
        cooldown_min = int(cfg.get("cooldown_minutos", 10))
        recientes = PanicEventModel.contar_recientes(empresa_id, residente_id, cooldown_min)
        if recientes >= cooldown_max:
            motivo = (f"Límite de activaciones alcanzado. "
                      f"Máximo {cooldown_max} en {cooldown_min} minutos.")
            # Registrar el intento fallido en el historial
            PanicEventModel.registrar(
                empresa_id, residente_id,
                resultado={"bloqueado": True, "motivo": motivo,
                           "externos": [], "directorio": []},
                ip=ip, nombre_residente=nombre_residente,
                nombre_empresa=nombre_empresa,
            )
            return False, motivo

        cliente    = _twilio_client()
        resultado  = {"externos": [], "directorio": [], "errores": []}

        canal_sms_on  = cfg.get("activo_sms",      True)
        canal_wa_on   = cfg.get("activo_whatsapp",  True)
        canal_call_on = cfg.get("activo_llamada",   True)

        tpl_sms      = cfg.get("mensaje_sms",      "") or MSG_DEFAULT_SMS
        tpl_whatsapp = cfg.get("mensaje_whatsapp", "") or MSG_DEFAULT_WHATSAPP
        tpl_llamada  = cfg.get("mensaje_llamada",  "") or MSG_DEFAULT_LLAMADA

        msg_sms       = _aplicar_vars(tpl_sms,      nombre_residente, nombre_empresa, torre, apartamento)
        msg_whatsapp  = _aplicar_vars(tpl_whatsapp, nombre_residente, nombre_empresa, torre, apartamento)
        texto_llamada = _aplicar_vars(tpl_llamada,  nombre_residente, nombre_empresa, torre, apartamento)

        twiml_conf = _construir_twiml(texto_llamada) if canal_call_on else None

        # Deduplicación: un mismo número NO recibe 2 veces el mismo canal en este
        # evento. El primer envío va normal; el duplicado queda "fallido" con la
        # causa clara (no se envía a Twilio). Aplica a SMS, WhatsApp y llamada.
        vistos_canal = set()
        def _enviar_dedup(canal, num, enviar_fn):
            clave = (num, canal)
            if clave in vistos_canal:
                return _resultado_duplicado(num, canal)
            vistos_canal.add(clave)
            return enviar_fn()

        # ── Contactos personales del usuario ──────────────────────────────
        try:
            contactos_personales = list(db["user_panic_contacts"].find({
                "usuario_id": ObjectId(residente_id),
                "empresa_id": ObjectId(empresa_id),
                "habilitado": True
            }))
            for c in contactos_personales:
                numero = _numero_completo(c.get("prefijo", "+57"), c.get("celular", ""))
                if not numero:
                    continue
                entry = {"nombre": c.get("nombre", ""), "numero": numero, "canales": {}}

                if c.get("habilitado_para_sms") and canal_sms_on:
                    entry["canales"]["sms"] = _enviar_dedup("sms", numero,
                        lambda: _enviar_sms(cliente, numero, msg_sms, c.get("nombre"), "",
                                            nombre_residente, nombre_empresa, _ts()))
                if c.get("habilitado_para_llamada") and canal_call_on and twiml_conf:
                    entry["canales"]["llamada"] = _enviar_dedup("llamada", numero,
                        lambda: _enviar_llamada(cliente, numero, twiml_conf, c.get("nombre"), "",
                                                nombre_residente, nombre_empresa, _ts()))
                if c.get("habilitado_para_whatsapp") and canal_wa_on:
                    entry["canales"]["whatsapp"] = _enviar_dedup("whatsapp", numero,
                        lambda: _enviar_whatsapp(cliente, numero, msg_whatsapp, c.get("nombre"), "",
                                                 nombre_residente, nombre_empresa, _ts()))

                if entry.get("canales"):
                    resultado["externos"].append(entry)
        except Exception as e:
            log.warning("Error procesando contactos personales: %s", e)

        # ── Contactos del directorio ──────────────────────────────────────
        for c in cfg.get("contactos_directorio", []):
            necesita_sms      = bool(c.get("habilitado_para_sms"))      and canal_sms_on
            necesita_llamar   = bool(c.get("habilitado_para_llamar"))   and canal_call_on
            necesita_whatsapp = bool(c.get("habilitado_para_whatsapp")) and canal_wa_on
            if not any([necesita_sms, necesita_llamar, necesita_whatsapp]):
                continue

            telefonos = _telefonos_contacto(c.get("contacto_id", ""))
            tel = next((t for t in telefonos if t.get("numero", "").strip()), None)
            if not tel:
                continue

            numero = _numero_completo(tel.get("prefijo", "+57"), tel.get("numero", ""))
            entry  = {"nombre": c.get("nombre", ""), "numero": numero, "canales": {}}

            if necesita_sms:
                entry["canales"]["sms"] = _enviar_dedup("sms", numero,
                    lambda: _enviar_sms(cliente, numero, msg_sms, c.get("nombre"), "",
                                        nombre_residente, nombre_empresa, _ts()))
            if necesita_llamar and twiml_conf:
                entry["canales"]["llamada"] = _enviar_dedup("llamada", numero,
                    lambda: _enviar_llamada(cliente, numero, twiml_conf, c.get("nombre"), "",
                                            nombre_residente, nombre_empresa, _ts()))
            if necesita_whatsapp:
                entry["canales"]["whatsapp"] = _enviar_dedup("whatsapp", numero,
                    lambda: _enviar_whatsapp(cliente, numero, msg_whatsapp, c.get("nombre"), "",
                                             nombre_residente, nombre_empresa, _ts()))

            resultado["directorio"].append(entry)

        event_id = PanicEventModel.registrar(
            empresa_id, residente_id, resultado, ip,
            nombre_residente=nombre_residente, nombre_empresa=nombre_empresa,
        )
        return True, {"event_id": event_id, "resultado": resultado}
