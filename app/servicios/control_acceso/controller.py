"""
app/servicios/control_acceso/controller.py
───────────────────────────────────────────
Lógica de negocio del Control de Acceso.

REUTILIZA la integración Twilio del botón de pánico (solo importa, no modifica):
  _twilio_client, TWILIO_FROM, TWILIO_WA_FROM, TWILIO_WEBHOOK_URL

Notificaciones en hilo (threading) para no bloquear la respuesta en portería.
"""

import os
import logging
import threading
import xml.sax.saxutils as _xml
from urllib.parse import urlparse

from app.servicios.control_acceso.model import (
    AccessCredentialModel, AccessLogModel, CoaccionModel, _ahora_bogota,
)
from app.servicios.control_acceso.config_model import CaConfigModel, CaBlacklistModel

# Reuso de la base Twilio ya probada (sin tocarla)
from app.servicios.boton_panico.controller import (
    _twilio_client, TWILIO_FROM, TWILIO_WA_FROM, TWILIO_WEBHOOK_URL,
)

log = logging.getLogger(__name__)

# Base pública (ngrok) derivada de la URL de webhook ya configurada
_p = urlparse(TWILIO_WEBHOOK_URL or "")
PUBLIC_BASE = f"{_p.scheme}://{_p.netloc}" if _p.netloc else "http://localhost:5000"

# Número del cuadrante de policía / supervisor (configurable por conjunto más adelante)
SEGURIDAD_SMS_DEFAULT = os.environ.get("CONTROL_ACCESO_SMS_SEGURIDAD", "")


def _async(fn, *args, **kwargs):
    """Ejecuta una función en un hilo daemon (no bloquea la portería)."""
    threading.Thread(target=lambda: _safe(fn, *args, **kwargs), daemon=True).start()


def _safe(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as e:
        log.warning("control_acceso async error: %s", str(e)[:160])


# ── Notificaciones Twilio ───────────────────────────────────────────────────
def _enviar_whatsapp(numero: str, cuerpo: str):
    cliente = _twilio_client()
    if not cliente or not TWILIO_WA_FROM or not numero:
        log.info("[MOCK] WhatsApp rechazo → %s", numero)
        return
    cliente.messages.create(to=f"whatsapp:{numero}", from_=TWILIO_WA_FROM, body=cuerpo)


def _enviar_sms(numero: str, cuerpo: str):
    cliente = _twilio_client()
    if not cliente or not TWILIO_FROM or not numero:
        log.info("[MOCK] SMS seguridad → %s", numero)
        return
    cliente.messages.create(to=numero, from_=TWILIO_FROM, body=cuerpo)


def _num(prefijo: str, tel: str) -> str:
    tel = (tel or "").strip()
    if not tel:
        return ""
    if tel.startswith("+"):
        return tel
    return f"{prefijo or '+57'}{tel}"


class AccessController:

    # ── Validación principal en portería (QR / PIN 6 chars) ────────────────
    @staticmethod
    def validar_acceso(conjunto_id: str, codigo: str, vigilante_id: str = "",
                       conjunto_nombre: str = "", conjunto_direccion: str = "") -> dict:
        """Valida un código en portería. Maneja coacción, vigencia y ventana de
        tiempo. Devuelve dict con `resultado` y los datos para la pantalla."""
        codigo = (codigo or "").strip().upper()
        ahora = _ahora_bogota()

        # 0) LOCKDOWN — bloquea todo ingreso cuando está activo
        if CaConfigModel.lockdown_activo(conjunto_id):
            AccessLogModel.registrar(conjunto_id, metodo="PIN", estado="rechazado",
                                     vigilante_id=vigilante_id,
                                     detalle="Acceso bloqueado — Modo Lockdown activo")
            return {"resultado": "RECHAZADO",
                    "motivo": "⛔ MODO EMERGENCIA ACTIVO — Todos los accesos bloqueados",
                    "lockdown": True}

        # 1) ¿Es un PIN de COACCIÓN de algún residente del conjunto?
        coaccion = CoaccionModel.buscar_por_pin(conjunto_id, codigo)
        if coaccion:
            return AccessController._procesar_coaccion(
                conjunto_id, coaccion, vigilante_id, conjunto_nombre, conjunto_direccion)

        # 1b) BLACKLIST — documento del visitante bloqueado
        # (solo si el código pertenece a una credencial ya existente)

        # 2) Buscar credencial por código
        cred = AccessCredentialModel.buscar_por_codigo(conjunto_id, codigo)
        if not cred:
            AccessLogModel.registrar(conjunto_id, metodo="PIN", estado="rechazado",
                                     vigilante_id=vigilante_id, detalle="Código inválido")
            return {"resultado": "RECHAZADO", "motivo": "Código no válido o inexistente"}

        visitante = cred.get("visitante", {})
        unidad    = cred.get("unidad", {})

        # 2b) Verificar blacklist por documento del visitante
        doc_visitante = (visitante.get("documento") or "").strip()
        if doc_visitante and CaBlacklistModel.esta_bloqueado(conjunto_id, doc_visitante):
            AccessLogModel.registrar(conjunto_id, visitante=visitante, unidad=unidad,
                                     metodo=cred.get("metodo_autenticacion", "QR"),
                                     estado="rechazado", credencial_id=cred["_id"],
                                     vigilante_id=vigilante_id,
                                     detalle="Visitante en lista negra")
            return {"resultado": "RECHAZADO",
                    "motivo": "🚫 Persona en lista negra — Acceso denegado",
                    "visitante": visitante}

        # 3) Vigencia
        if not AccessCredentialModel.vigencia_ok(cred, ahora):
            AccessLogModel.registrar(conjunto_id, visitante=visitante, unidad=unidad,
                                     metodo=cred.get("metodo_autenticacion", "QR"),
                                     estado="rechazado", credencial_id=cred["_id"],
                                     vigilante_id=vigilante_id, detalle="Fuera de vigencia")
            return {"resultado": "RECHAZADO", "motivo": "Credencial vencida o aún no vigente",
                    "visitante": visitante, "unidad": unidad}

        # 4) Ventana de tiempo (solo recurrentes)
        if not AccessCredentialModel.ventana_tiempo_ok(cred, ahora):
            AccessLogModel.registrar(conjunto_id, visitante=visitante, unidad=unidad,
                                     metodo=cred.get("metodo_autenticacion", "QR"),
                                     estado="rechazado", credencial_id=cred["_id"],
                                     vigilante_id=vigilante_id, detalle="Fuera de horario permitido")
            # Notificar al residente por WhatsApp (async)
            AccessController._notificar_fuera_horario(cred, visitante, unidad, ahora)
            return {"resultado": "RECHAZADO_HORARIO",
                    "motivo": "Fuera del horario permitido",
                    "visitante": visitante, "unidad": unidad}

        # 5) OK → autorizado
        AccessLogModel.registrar(conjunto_id, visitante=visitante, unidad=unidad,
                                 metodo=cred.get("metodo_autenticacion", "QR"),
                                 estado="autorizado", credencial_id=cred["_id"],
                                 vigilante_id=vigilante_id, detalle="Acceso autorizado")

        # Notificar al residente por WhatsApp (async, no bloquea portería)
        _async(AccessController._notificar_residente_ingreso,
               conjunto_id, cred, visitante, unidad, ahora)

        return {"resultado": "AUTORIZADO", "visitante": visitante, "unidad": unidad,
                "tipo_credencial": cred.get("tipo_credencial")}

    # ── Coacción (acceso bajo amenaza) ─────────────────────────────────────
    @staticmethod
    def _procesar_coaccion(conjunto_id, coaccion, vigilante_id, conjunto_nombre, conjunto_direccion):
        u = coaccion.get("user", {}) or {}
        a = coaccion.get("asociacion", {}) or {}
        unidad = {"torre": a.get("torre", ""), "apartamento": a.get("apartamento", ""),
                  "bloque": a.get("unidad", "")}
        residente = f"{u.get('nombres','')} {u.get('apellidos','')}".strip()

        log_id = AccessLogModel.registrar(
            conjunto_id, unidad=unidad, metodo="PIN", estado="coaccion",
            coaccion_activa=True, vigilante_id=vigilante_id,
            detalle=f"PIN de coacción de {residente}")

        # SMS de urgencia a seguridad (async, no bloquea)
        ubic = f"Torre {unidad['torre']} Apto {unidad['apartamento']}".strip()
        mensaje = (f"¡EMERGENCIA DE SEGURIDAD! Acceso bajo coaccion en desarrollo. "
                   f"Conjunto: {conjunto_nombre or 'N/D'}, Ubicacion: {conjunto_direccion or 'N/D'}, "
                   f"Unidad: {ubic}. Proceder segun protocolo de seguridad armada.")
        if SEGURIDAD_SMS_DEFAULT:
            _async(_enviar_sms, SEGURIDAD_SMS_DEFAULT, mensaje)

        # Respuesta DUAL: a la pantalla se le dice "autorizado" (genérico)
        return {"resultado": "AUTORIZADO", "coaccion": True, "log_id": log_id,
                "mensaje_pantalla": "Acceso Autorizado. Bienvenido."}

    @staticmethod
    def _notificar_residente_ingreso(conjunto_id, cred, visitante, unidad, ahora):
        """WhatsApp al residente cuando su visita es autorizada en portería."""
        cfg = CaConfigModel.obtener(conjunto_id)
        if not cfg.get("notificaciones", {}).get("avisar_residente_ingreso", True):
            return
        from app import db
        sid = cred.get("solicitante_id")
        if not sid:
            return
        u = db["users"].find_one({"_id": sid}, {"telefono": 1, "nombres": 1}) or {}
        numero = _num("+57", u.get("telefono", ""))
        if not numero:
            return
        apto  = unidad.get("apartamento") or unidad.get("bloque") or ""
        torre = unidad.get("torre") or ""
        loc   = f"Torre {torre} - Apto {apto}".strip(" -")
        hora  = ahora.strftime("%I:%M %p")
        msg   = (f"🏠 *Nidus Control de Acceso*\n"
                 f"Tu visita *{visitante.get('nombre', 'visitante')}* "
                 f"acaba de ingresar al conjunto a las {hora}.\n"
                 f"Unidad: {loc}")
        _async(_enviar_whatsapp, numero, msg)

    @staticmethod
    def notificar_lockdown(conjunto_id: str):
        """Envía WhatsApp + llamada a los números de emergencia del conjunto."""
        from app import db
        cfg = CaConfigModel.obtener(conjunto_id)
        lockdown_cfg = cfg.get("lockdown", {})
        numeros = lockdown_cfg.get("numeros_emergencia", [])
        empresa = db["empresas"].find_one({"_id": __import__('bson').ObjectId(conjunto_id)},
                                          {"razon_social": 1, "nombre": 1}) or {}
        nombre_conj = empresa.get("razon_social") or empresa.get("nombre") or "Conjunto"
        msg = (f"🔴 *ALERTA LOCKDOWN — {nombre_conj}*\n"
               f"Se ha activado el modo de emergencia. "
               f"TODOS los accesos y salidas están bloqueados. "
               f"Proceder según protocolo de seguridad.")
        for num in numeros:
            num_fmt = _num("+57", num)
            if not num_fmt:
                continue
            if lockdown_cfg.get("notificar_whatsapp", True):
                _safe(_enviar_whatsapp, num_fmt, msg)
            if lockdown_cfg.get("notificar_llamada", True):
                _safe(AccessController._llamada_lockdown, num_fmt, nombre_conj)

    @staticmethod
    def _llamada_lockdown(numero: str, nombre_conj: str):
        cliente = _twilio_client()
        if not cliente or not TWILIO_FROM:
            return
        texto = (f"Alerta de emergencia en {nombre_conj}. "
                 f"Se ha activado el modo lockdown. "
                 f"Todos los accesos están bloqueados. "
                 f"Proceda según el protocolo de seguridad inmediatamente.")
        twiml = (f'<?xml version="1.0" encoding="UTF-8"?>'
                 f'<Response><Say language="es-US" voice="Polly.Lupe">'
                 f'{_xml.escape(texto)}</Say></Response>')
        from twilio.twiml.voice_response import VoiceResponse
        import base64
        twiml_url = (f"http://twimlets.com/echo?Twiml="
                     + __import__('urllib.parse', fromlist=['quote']).parse.quote(twiml))
        try:
            cliente.calls.create(to=numero, from_=TWILIO_FROM, twiml=twiml)
        except Exception as e:
            log.warning("lockdown call error: %s", str(e)[:120])

    @staticmethod
    def _notificar_fuera_horario(cred, visitante, unidad, ahora):
        # Teléfono del residente solicitante
        from app import db
        sid = cred.get("solicitante_id")
        numero = ""
        if sid:
            u = db["users"].find_one({"_id": sid}, {"telefono": 1})
            numero = _num("+57", (u or {}).get("telefono", ""))
        apto = unidad.get("apartamento", "") or unidad.get("bloque", "")
        msg = (f"Alerta: El visitante {visitante.get('nombre','')} intento ingresar a la unidad "
               f"{apto} fuera del horario permitido (Intento: {ahora.strftime('%d/%m/%Y %H:%M')}). "
               f"Acceso Bloqueado.")
        if numero:
            _async(_enviar_whatsapp, numero, msg)

    # ── Ingreso manual rápido ──────────────────────────────────────────────
    @staticmethod
    def ingreso_manual(conjunto_id: str, nombre: str, documento: str, unidad: dict,
                       vigilante_id: str = "") -> dict:
        visitante = {"nombre": nombre, "documento": documento}
        log_id = AccessLogModel.registrar(
            conjunto_id, visitante=visitante, unidad=unidad, metodo="MANUAL",
            estado="ingreso_manual", vigilante_id=vigilante_id,
            detalle="Ingreso manual rápido")
        return {"resultado": "INGRESO_MANUAL", "log_id": log_id,
                "visitante": visitante, "unidad": unidad}

    # ── Citofonía virtual (Twilio Voice + DTMF) ────────────────────────────
    @staticmethod
    def iniciar_citofonia(conjunto_id: str, log_id: str, numero_residente: str,
                          nombre_visita: str) -> dict:
        cliente = _twilio_client()
        if not cliente or not TWILIO_FROM or not numero_residente:
            return {"ok": False, "error": "Sin Twilio o sin número del residente"}
        # URL pública del TwiML (Gather) — reusa la base de ngrok ya configurada
        twiml_url = (f"{PUBLIC_BASE}/servicios/control_acceso/citofonia/twiml"
                     f"?log_id={log_id}&visita={_xml.quoteattr(nombre_visita)[1:-1]}")
        try:
            call = cliente.calls.create(to=numero_residente, from_=TWILIO_FROM, url=twiml_url)
            return {"ok": True, "sid": call.sid}
        except Exception as e:
            return {"ok": False, "error": str(e)[:160]}

    @staticmethod
    def twiml_citofonia(log_id: str, nombre_visita: str) -> str:
        """TwiML con <Gather> para que el residente presione 1 (autorizar) o 2."""
        action = f"{PUBLIC_BASE}/servicios/control_acceso/citofonia/callback?log_id={log_id}"
        texto = (f"Tiene una visita de {nombre_visita or 'un visitante'} en porteria. "
                 f"Presione 1 para autorizar el ingreso, o presione 2 para rechazarlo.")
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            f'<Gather numDigits="1" action="{_xml.escape(action)}" method="POST" timeout="15">'
            f'<Say language="es-US" voice="Polly.Lupe">{_xml.escape(texto)}</Say>'
            '</Gather>'
            '<Say language="es-US" voice="Polly.Lupe">No se recibio respuesta. Adios.</Say>'
            '</Response>'
        )

    @staticmethod
    def procesar_dtmf(log_id: str, digito: str) -> str:
        """Procesa el dígito del residente y actualiza el log. Devuelve TwiML."""
        if digito == "1":
            AccessLogModel.actualizar_estado(log_id, "autorizado_citofonia",
                                             "Autorizado por el residente (tecla 1)")
            texto = "Ingreso autorizado. Gracias."
        elif digito == "2":
            AccessLogModel.actualizar_estado(log_id, "rechazado_citofonia",
                                             "Rechazado por el residente (tecla 2)")
            texto = "Ingreso rechazado. Gracias."
        else:
            texto = "Opcion no valida."
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                f'<Response><Say language="es-US" voice="Polly.Lupe">{_xml.escape(texto)}</Say></Response>')
