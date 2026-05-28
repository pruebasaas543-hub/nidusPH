"""
app/servicios/boton_panico/controller.py
Lógica de negocio para el módulo Botón de Pánico.
"""

import os
import logging
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape  # fallback si twilio.twiml no disponible
from bson import ObjectId

from app import db
from app.servicios.boton_panico.model import PanicConfigModel, PanicEventModel

log = logging.getLogger(__name__)

TWILIO_FROM               = os.environ.get("TWILIO_PHONE_NUMBER", "")
TWILIO_WA_FROM            = os.environ.get("TWILIO_WHATSAPP_FROM", "")
TWILIO_PANIC_TEMPLATE_SID = os.environ.get("TWILIO_PANIC_TEMPLATE_SID", "")

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


def _aplicar_vars(texto: str, nombre_residente: str, nombre_empresa: str) -> str:
    return (texto
            .replace("{nombre_residente}", nombre_residente)
            .replace("{nombre_empresa}", nombre_empresa))


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
        r.say(texto, voice="alice", language="es")
        r.pause(length=1)
        r.say(texto, voice="alice", language="es")
        r.hangup()
        twiml = str(r)
        log.info("TwiML generado: %s", twiml)
        return twiml
    except ImportError:
        texto_xml = xml_escape(texto)
        twiml = (
            '<Response>'
            f'<Say voice="alice" language="es">{texto_xml}</Say>'
            f'<Pause length="1"/>'
            f'<Say voice="alice" language="es">{texto_xml}</Say>'
            f'<Hangup/></Response>'
        )
        log.info("TwiML generado (fallback): %s", twiml)
        return twiml


def _numero_completo(prefijo: str, numero: str) -> str:
    """Construye número E.164: prefijo + número (sin espacios ni guiones)."""
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


def _enviar_sms(cliente, numero: str, mensaje: str) -> dict:
    if not cliente or not TWILIO_FROM:
        log.info("[MOCK] SMS → %s", numero)
        return {"numero": numero, "estado": "mock", "detalle": "Sin credenciales Twilio"}
    try:
        msg = cliente.messages.create(to=numero, from_=TWILIO_FROM, body=mensaje)
        log.info("SMS enviado → %s (SID=%s)", numero, msg.sid)
        return {"numero": numero, "estado": "enviado", "sid": msg.sid}
    except Exception as e:
        log.error("SMS error → %s: %s", numero, e)
        return {"numero": numero, "estado": "error", "detalle": str(e)}


def _enviar_llamada(cliente, numero: str, twiml: str) -> dict:
    if not cliente or not TWILIO_FROM:
        log.info("[MOCK] CALL → %s", numero)
        return {"numero": numero, "estado": "mock", "detalle": "Sin credenciales Twilio"}
    try:
        call = cliente.calls.create(to=numero, from_=TWILIO_FROM, twiml=twiml)
        log.info("Llamada iniciada → %s (SID=%s)", numero, call.sid)
        return {"numero": numero, "estado": "iniciado", "sid": call.sid}
    except Exception as e:
        log.error("Call error → %s: %s", numero, e)
        return {"numero": numero, "estado": "error", "detalle": str(e)}


def _enviar_whatsapp(cliente, numero: str, cuerpo: str) -> dict:
    if not cliente or not TWILIO_WA_FROM:
        log.info("[MOCK] WhatsApp → %s", numero)
        return {"numero": numero, "estado": "mock", "detalle": "Sin credenciales Twilio"}
    try:
        kwargs = {"to": f"whatsapp:{numero}", "from_": TWILIO_WA_FROM}
        if TWILIO_PANIC_TEMPLATE_SID:
            kwargs["content_sid"]       = TWILIO_PANIC_TEMPLATE_SID
            kwargs["content_variables"] = f'{{"1":"{cuerpo}"}}'
        else:
            kwargs["body"] = cuerpo
        msg = cliente.messages.create(**kwargs)
        log.info("WhatsApp enviado → %s (SID=%s)", numero, msg.sid)
        return {"numero": numero, "estado": "enviado", "sid": msg.sid}
    except Exception as e:
        log.error("WhatsApp error → %s: %s", numero, e)
        return {"numero": numero, "estado": "error", "detalle": str(e)}


class PanicController:

    @staticmethod
    def obtener_config(empresa_id: str, residente_id: str):
        cfg = PanicConfigModel.obtener(empresa_id, residente_id)
        if not cfg:
            return True, {"contactos_externos": [], "contactos_directorio": []}
        return True, cfg

    @staticmethod
    def guardar_config(empresa_id: str, residente_id: str, datos: dict):
        externos = datos.get("contactos_externos", [])
        if len(externos) > 2:
            return False, "Máximo 2 contactos externos permitidos"
        for c in externos:
            if not str(c.get("nombre", "")).strip():
                return False, "Cada contacto externo debe tener nombre"
            if not str(c.get("celular", "")).strip():
                return False, "Cada contacto externo debe tener celular"
            if not c.get("tipo_notificacion"):
                return False, f"Define al menos un tipo de notificación para '{c.get('nombre')}'"

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

        mensaje_llamada = str(datos.get("mensaje_llamada", "")).strip()
        PanicConfigModel.guardar(empresa_id, residente_id, externos, directorio, mensaje_llamada)
        return True, "Configuración guardada"

    @staticmethod
    def trigger(empresa_id: str, residente_id: str,
                nombre_residente: str, nombre_empresa: str, ip: str = ""):

        cfg = PanicConfigModel.obtener(empresa_id, residente_id)
        if not cfg:
            return False, "Sin configuración de pánico. Configura tus contactos primero."

        cliente     = _twilio_client()
        resultado   = {"externos": [], "directorio": [], "errores": []}

        cfg_empresa  = db["panic_empresa_config"].find_one({"empresa_id": ObjectId(empresa_id)}) or {}
        tpl_sms      = cfg_empresa.get("mensaje_sms",      "").strip() or MSG_DEFAULT_SMS
        tpl_whatsapp = cfg_empresa.get("mensaje_whatsapp", "").strip() or MSG_DEFAULT_WHATSAPP
        tpl_llamada  = cfg_empresa.get("mensaje_llamada",  "").strip() or MSG_DEFAULT_LLAMADA

        msg_sms      = _aplicar_vars(tpl_sms,      nombre_residente, nombre_empresa)
        msg_whatsapp = _aplicar_vars(tpl_whatsapp, nombre_residente, nombre_empresa)
        texto_llamada = _aplicar_vars(tpl_llamada, nombre_residente, nombre_empresa)

        twiml_conf = _construir_twiml(texto_llamada)

        # ── Contactos externos ────────────────────────────────────────────
        for c in cfg.get("contactos_externos", []):
            numero = _numero_completo(c.get("prefijo", "+57"), c.get("celular", ""))
            if not numero:
                continue
            tipos  = c.get("tipo_notificacion", [])
            entry  = {"nombre": c.get("nombre", ""), "numero": numero, "canales": {}}

            if "sms" in tipos:
                entry["canales"]["sms"] = _enviar_sms(cliente, numero, msg_sms)
            if "llamada" in tipos:
                entry["canales"]["llamada"] = _enviar_llamada(cliente, numero, twiml_conf)
            if "whatsapp" in tipos:
                entry["canales"]["whatsapp"] = _enviar_whatsapp(cliente, numero, msg_whatsapp)

            resultado["externos"].append(entry)

        # ── Contactos del directorio ──────────────────────────────────────
        for c in cfg.get("contactos_directorio", []):
            necesita_sms      = bool(c.get("habilitado_para_sms"))
            necesita_llamar   = bool(c.get("habilitado_para_llamar"))
            necesita_whatsapp = bool(c.get("habilitado_para_whatsapp"))
            if not any([necesita_sms, necesita_llamar, necesita_whatsapp]):
                continue

            telefonos = _telefonos_contacto(c.get("contacto_id", ""))
            tel = next((t for t in telefonos if t.get("numero", "").strip()), None)
            if not tel:
                continue

            numero = _numero_completo(tel.get("prefijo", "+57"), tel.get("numero", ""))
            entry  = {"nombre": c.get("nombre", ""), "numero": numero, "canales": {}}

            if necesita_sms:
                entry["canales"]["sms"] = _enviar_sms(cliente, numero, msg_sms)
            if necesita_llamar:
                entry["canales"]["llamada"] = _enviar_llamada(cliente, numero, twiml_conf)
            if necesita_whatsapp:
                entry["canales"]["whatsapp"] = _enviar_whatsapp(cliente, numero, msg_whatsapp)

            resultado["directorio"].append(entry)

        event_id = PanicEventModel.registrar(empresa_id, residente_id, resultado, ip)
        return True, {"event_id": event_id, "resultado": resultado}
