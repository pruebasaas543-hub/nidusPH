"""
app/configuracion/boton_panico/routes.py
Endpoints de administración del módulo Botón de Pánico.
Prefijo: /config/boton_panico
"""

from flask import Blueprint, request
from bson import ObjectId

from app import db
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.servicios.boton_panico.model import PanicConfigModel, PanicEventModel
from app.servicios.boton_panico.controller import MSG_DEFAULT_SMS, MSG_DEFAULT_WHATSAPP, MSG_DEFAULT_LLAMADA

panico_cfg_bp = Blueprint("panico_cfg", __name__, url_prefix="/config/boton_panico")

DEFAULTS = {
    "llamada":  MSG_DEFAULT_LLAMADA,
    "sms":      MSG_DEFAULT_SMS,
    "whatsapp": MSG_DEFAULT_WHATSAPP,
}
CAMPOS = {"llamada": "mensaje_llamada", "sms": "mensaje_sms", "whatsapp": "mensaje_whatsapp"}


def _empresa_id():
    return request.args.get("propiedad_id", "").strip()


@panico_cfg_bp.route("/mensajes", methods=["GET"])
@requiere_superadmin
def obtener_mensajes():
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    try:
        msgs = PanicConfigModel.obtener_mensajes_empresa(eid)
        sms      = msgs["mensaje_sms"]
        whatsapp = msgs["mensaje_whatsapp"]
        llamada  = msgs["mensaje_llamada"]
        return ok({
            "sms":        sms      or MSG_DEFAULT_SMS,
            "whatsapp":   whatsapp or MSG_DEFAULT_WHATSAPP,
            "llamada":    llamada  or MSG_DEFAULT_LLAMADA,
            "es_default": {
                "sms":      not sms,
                "whatsapp": not whatsapp,
                "llamada":  not llamada,
            },
            "activo": {
                "sms":      msgs.get("activo_sms",      True),
                "whatsapp": msgs.get("activo_whatsapp", True),
                "llamada":  msgs.get("activo_llamada",  True),
            },
            "cooldown_max":     msgs.get("cooldown_max",     2),
            "cooldown_minutos": msgs.get("cooldown_minutos", 10),
            "creado_en":      msgs.get("creado_en"),
            "actualizado_en": msgs.get("actualizado_en"),
        })
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/mensajes/<tipo>", methods=["PUT"])
@requiere_superadmin
def guardar_mensaje(tipo):
    if tipo not in CAMPOS:
        return err("Tipo inválido. Use: llamada, sms, whatsapp", 400)
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    datos = request.get_json(silent=True) or {}
    mensaje = str(datos.get("mensaje", "")).strip()
    if not mensaje:
        return err("El mensaje no puede estar vacío", 400)
    try:
        PanicConfigModel.guardar_mensaje_empresa(eid, CAMPOS[tipo], mensaje)
        return ok(mensaje="Mensaje guardado")
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/mensajes/<tipo>", methods=["DELETE"])
@requiere_superadmin
def restablecer_mensaje(tipo):
    if tipo not in CAMPOS:
        return err("Tipo inválido", 400)
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    try:
        PanicConfigModel.limpiar_mensaje_empresa(eid, CAMPOS[tipo])
        return ok({"default": DEFAULTS[tipo]}, mensaje="Restablecido al mensaje predeterminado")
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/mensajes/<tipo>/activo", methods=["PATCH"])
@requiere_superadmin
def cambiar_activo_canal(tipo):
    if tipo not in CAMPOS:
        return err("Tipo inválido. Use: llamada, sms, whatsapp", 400)
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    datos  = request.get_json(silent=True) or {}
    activo = bool(datos.get("activo", True))
    try:
        PanicConfigModel.guardar_activo_canal(eid, tipo, activo)
        estado = "activado" if activo else "desactivado"
        return ok(mensaje=f"Canal {tipo} {estado}")
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/canales", methods=["PUT"])
@requiere_superadmin
def guardar_canales():
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    datos = request.get_json(silent=True) or {}
    try:
        for tipo in ("sms", "whatsapp", "llamada"):
            if tipo in datos:
                PanicConfigModel.guardar_activo_canal(eid, tipo, bool(datos[tipo]))
        return ok(mensaje="Canales guardados")
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/cooldown", methods=["GET"])
@requiere_superadmin
def obtener_cooldown():
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    try:
        doc = PanicConfigModel.obtener(eid)
        return ok({
            "cooldown_max":     doc.get("cooldown_max",     2),
            "cooldown_minutos": doc.get("cooldown_minutos", 10),
        })
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/cooldown", methods=["PUT"])
@requiere_superadmin
def guardar_cooldown():
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    datos = request.get_json(silent=True) or {}
    try:
        cooldown_max = int(datos.get("cooldown_max", 2))
        cooldown_min = int(datos.get("cooldown_minutos", 10))
    except (ValueError, TypeError):
        return err("Valores inválidos. Se esperan enteros.", 400)
    if not (1 <= cooldown_max <= 10):
        return err("cooldown_max debe estar entre 1 y 10", 400)
    if not (1 <= cooldown_min <= 60):
        return err("cooldown_minutos debe estar entre 1 y 60", 400)
    try:
        PanicConfigModel.guardar_cooldown(eid, cooldown_max, cooldown_min)
        return ok(mensaje="Configuración de cooldown guardada")
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/contactos", methods=["GET"])
@requiere_superadmin
def listar_contactos_vinculados():
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    try:
        contactos = list(
            db["directorio_contactos"].find(
                {
                    "empresa_id":                   ObjectId(eid),
                    "activo":                       True,
                    "vinculado_al_boton_de_panico": True,
                },
                {"nombre": 1, "cargo_titulo": 1, "bloque": 1, "telefonos": 1,
                 "es_visible_para_seguridad": 1, "es_visible_para_administracion": 1},
            ).sort("nombre", 1)
        )
        return ok(serializar(contactos))
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/eventos", methods=["GET"])
@requiere_superadmin
def listar_eventos():
    from datetime import datetime, timezone
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    try:
        limite    = min(int(request.args.get("limite", 20)), 200)
        fecha_ini = request.args.get("fecha_ini", "").strip()
        fecha_fin = request.args.get("fecha_fin", "").strip()
        filtro_fechas = {}
        if fecha_ini:
            filtro_fechas["$gte"] = datetime.fromisoformat(fecha_ini).replace(tzinfo=timezone.utc)
        if fecha_fin:
            filtro_fechas["$lte"] = datetime.fromisoformat(fecha_fin).replace(tzinfo=timezone.utc)
        eventos = PanicEventModel.listar_por_empresa(eid, limite=limite, filtro_fechas=filtro_fechas or None)
        return ok(serializar(eventos))
    except ValueError:
        return err("Formato de fecha inválido. Use YYYY-MM-DD", 400)
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/stats", methods=["GET"])
@requiere_superadmin
def stats():
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    try:
        total_contactos = db["directorio_contactos"].count_documents({
            "empresa_id":                   ObjectId(eid),
            "activo":                       True,
            "vinculado_al_boton_de_panico": True,
        })
        total_eventos = db["panic_events"].count_documents({
            "empresa_id": ObjectId(eid),
        })
        ultimo = db["panic_events"].find_one(
            {"empresa_id": ObjectId(eid)},
            {"activado_en": 1, "residente_id": 1},
            sort=[("activado_en", -1)],
        )
        return ok({
            "total_contactos": total_contactos,
            "total_eventos":   total_eventos,
            "ultimo_evento":   serializar(ultimo) if ultimo else None,
        })
    except Exception as e:
        return err(str(e))
