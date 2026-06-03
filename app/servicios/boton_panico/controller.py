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
    PanicConfigModel, PanicEventModel, MAPA_ESTADOS
)

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


def _aplicar_vars(texto: str, nombre_residente: str, nombre_empresa: str,
                  torre: str = "", apartamento: str = "") -> str:
    return (texto
            .replace("{nombre_residente}", nombre_residente)
            .replace("{nombre_empresa}",   nombre_empresa)
            .replace("{torre}",            torre or "")
            .replace("{apartamento}",      apartamento or ""))


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


def _enviar_sms(cliente, numero: str, mensaje: str) -> dict:
    if not cliente or not TWILIO_FROM:
        log.info("[MOCK] SMS → %s", numero)
        return {"numero": numero, "estado": "mock", "detalle": "Sin credenciales Twilio",
                "historial": [{"estado": "mock", "en": _ts()}]}
    try:
        msg = cliente.messages.create(to=numero, from_=TWILIO_FROM, body=mensaje)
        log.info("SMS enviado → %s (SID=%s)", numero, msg.sid)
        estado_raw = msg.status or "queued"
        estado_ini = MAPA_ESTADOS.get(estado_raw.lower(), estado_raw)
        return {"numero": numero, "estado": estado_ini, "sid": msg.sid,
                "historial": [{"estado": estado_ini, "en": _ts()}]}
    except Exception as e:
        log.error("SMS error → %s: %s", numero, e)
        return {"numero": numero, "estado": "fallido", "detalle": str(e),
                "historial": [{"estado": "fallido", "en": _ts(), "detalle": str(e)}]}


def _enviar_llamada(cliente, numero: str, twiml: str) -> dict:
    if not cliente or not TWILIO_FROM:
        log.info("[MOCK] CALL → %s", numero)
        return {"numero": numero, "estado": "mock", "detalle": "Sin credenciales Twilio",
                "historial": [{"estado": "mock", "en": _ts()}]}
    try:
        call = cliente.calls.create(to=numero, from_=TWILIO_FROM, twiml=twiml)
        log.info("Llamada iniciada → %s (SID=%s)", numero, call.sid)
        estado_raw = call.status or "queued"
        estado_ini = MAPA_ESTADOS.get(estado_raw.lower(), estado_raw)
        return {"numero": numero, "estado": estado_ini, "sid": call.sid,
                "historial": [{"estado": estado_ini, "en": _ts()}]}
    except Exception as e:
        log.error("Call error → %s: %s", numero, e)
        return {"numero": numero, "estado": "fallido", "detalle": str(e),
                "historial": [{"estado": "fallido", "en": _ts(), "detalle": str(e)}]}


def _enviar_whatsapp(cliente, numero: str, cuerpo: str) -> dict:
    if not cliente or not TWILIO_WA_FROM:
        log.info("[MOCK] WhatsApp → %s", numero)
        return {"numero": numero, "estado": "mock", "detalle": "Sin credenciales Twilio",
                "historial": [{"estado": "mock", "en": _ts()}]}
    try:
        kwargs = {"to": f"whatsapp:{numero}", "from_": TWILIO_WA_FROM}
        if TWILIO_PANIC_TEMPLATE_SID:
            kwargs["content_sid"]       = TWILIO_PANIC_TEMPLATE_SID
            kwargs["content_variables"] = f'{{"1":"{cuerpo}"}}'
        else:
            kwargs["body"] = cuerpo
        msg = cliente.messages.create(**kwargs)
        log.info("WhatsApp enviado → %s (SID=%s)", numero, msg.sid)
        estado_raw = msg.status or "queued"
        estado_ini = MAPA_ESTADOS.get(estado_raw.lower(), estado_raw)
        return {"numero": numero, "estado": estado_ini, "sid": msg.sid,
                "historial": [{"estado": estado_ini, "en": _ts()}]}
    except Exception as e:
        log.error("WhatsApp error → %s: %s", numero, e)
        return {"numero": numero, "estado": "fallido", "detalle": str(e),
                "historial": [{"estado": "fallido", "en": _ts(), "detalle": str(e)}]}


class PanicController:

    @staticmethod
    def obtener_config(empresa_id: str):
        cfg = PanicConfigModel.obtener(empresa_id)
        return True, cfg or {"contactos_externos": [], "contactos_directorio": []}

    @staticmethod
    def guardar_config(empresa_id: str, datos: dict):
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

        PanicConfigModel.guardar_contactos(empresa_id, externos, directorio)
        return True, "Configuración guardada"

    @staticmethod
    def trigger(empresa_id: str, residente_id: str,
                nombre_residente: str, nombre_empresa: str, ip: str = "",
                torre: str = "", apartamento: str = ""):

        cfg = PanicConfigModel.obtener(empresa_id)
        if not cfg or (not cfg.get("contactos_externos") and not cfg.get("contactos_directorio")):
            return False, "Sin configuración de pánico. Configura los contactos primero."

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

        # ── Contactos externos ────────────────────────────────────────────
        for c in cfg.get("contactos_externos", []):
            numero = _numero_completo(c.get("prefijo", "+57"), c.get("celular", ""))
            if not numero:
                continue
            tipos  = c.get("tipo_notificacion", [])
            entry  = {"nombre": c.get("nombre", ""), "numero": numero, "canales": {}}

            if "sms" in tipos and canal_sms_on:
                entry["canales"]["sms"] = _enviar_sms(cliente, numero, msg_sms)
            if "llamada" in tipos and canal_call_on and twiml_conf:
                entry["canales"]["llamada"] = _enviar_llamada(cliente, numero, twiml_conf)
            if "whatsapp" in tipos and canal_wa_on:
                entry["canales"]["whatsapp"] = _enviar_whatsapp(cliente, numero, msg_whatsapp)

            resultado["externos"].append(entry)

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
                entry["canales"]["sms"] = _enviar_sms(cliente, numero, msg_sms)
            if necesita_llamar and twiml_conf:
                entry["canales"]["llamada"] = _enviar_llamada(cliente, numero, twiml_conf)
            if necesita_whatsapp:
                entry["canales"]["whatsapp"] = _enviar_whatsapp(cliente, numero, msg_whatsapp)

            resultado["directorio"].append(entry)

        event_id = PanicEventModel.registrar(
            empresa_id, residente_id, resultado, ip,
            nombre_residente=nombre_residente, nombre_empresa=nombre_empresa,
        )
        return True, {"event_id": event_id, "resultado": resultado}
