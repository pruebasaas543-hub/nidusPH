"""
app/servicios/boton_panico/routes.py
API REST del módulo Botón de Pánico.
Prefijo: /servicios/boton_panico
"""

from flask import Blueprint, request, session
from bson import ObjectId
from datetime import datetime, timezone

from app import db
from app.configuracion.utils import requiere_login, ok, err, serializar
from app.configuracion.roles.model import RolModel
from app.servicios.boton_panico.controller import PanicController
from app.servicios.boton_panico.model import PanicConfigModel, PanicEventModel

panico_bp = Blueprint("boton_panico", __name__, url_prefix="/servicios/boton_panico")


def _usuario():        return session.get("num_doc") or session.get("usuario_id", "sistema")
def _empresa_id():     return session.get("empresa_id", "")
def _nombre_res():     return session.get("nombres") or _usuario()
def _nombre_empresa(): return session.get("empresa_nombre") or "la propiedad"
def _es_sistema():     return session.get("rol", "") in RolModel.nombres_sistema()


def _requiere_sistema(f):
    from functools import wraps
    from flask import jsonify
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("num_doc"):
            return jsonify({"ok": False, "error": "No autenticado"}), 401
        if not _es_sistema():
            return jsonify({"ok": False, "error": "Sin permisos"}), 403
        return f(*args, **kwargs)
    return decorated


# ── Países / prefijos ─────────────────────────────────────────────────────

@panico_bp.route("/paises", methods=["GET"])
@requiere_login
def listar_paises():
    try:
        paises = list(db["paises_prefijos"].find(
            {}, {"nombre_pais": 1, "prefijo": 1, "bandera": 1, "longitud_celular_estandar": 1}
        ).sort("nombre_pais", 1))
        return ok(serializar(paises))
    except Exception as e:
        return err(str(e))


# ── Configuración del residente ───────────────────────────────────────────

@panico_bp.route("/config", methods=["GET"])
@requiere_login
def obtener_config():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    _, cfg = PanicController.obtener_config(eid)
    return ok(serializar(cfg))


@panico_bp.route("/config", methods=["PUT"])
@requiere_login
def guardar_config():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    datos = request.get_json(silent=True) or {}
    exito, resultado = PanicController.guardar_config(eid, datos)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


# ── Contactos del directorio habilitados para pánico ─────────────────────

@panico_bp.route("/directorio", methods=["GET"])
@requiere_login
def directorio_panico():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    try:
        contactos = list(
            db["directorio_contactos"].find(
                {
                    "empresa_id":                   ObjectId(eid),
                    "vinculado_al_boton_de_panico": True,
                },
                {"nombre": 1, "cargo_titulo": 1, "bloque": 1, "telefonos": 1},
            ).sort("nombre", 1)
        )
        return ok(serializar(contactos))
    except Exception as e:
        return err(str(e))


# ── Activar pánico ────────────────────────────────────────────────────────

@panico_bp.route("/trigger", methods=["POST"])
@requiere_login
def trigger():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)

    torre = ""
    apartamento = ""
    try:
        uid = session.get("usuario_id")
        if uid:
            asoc = db["asociaciones"].find_one({
                "user_id":    ObjectId(uid),
                "empresa_id": ObjectId(eid),
                "activo":     True,
            })
            if asoc:
                torre       = asoc.get("torre", "") or ""
                apartamento = asoc.get("apartamento", "") or ""
    except Exception:
        pass

    exito, resultado = PanicController.trigger(
        eid, _usuario(), _nombre_res(), _nombre_empresa(),
        request.remote_addr or "",
        torre=torre, apartamento=apartamento,
    )
    if not exito:
        return err(resultado)
    return ok(serializar(resultado))


# ── Historial del residente ───────────────────────────────────────────────

@panico_bp.route("/eventos", methods=["GET"])
@requiere_login
def listar_eventos():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    eventos = PanicEventModel.listar_por_residente(eid, _usuario(), limite=5)
    return ok(serializar(eventos))


# ══════════════════════════════════════════════════════════════════════════
# Endpoints exclusivos para roles es_sistema = true
# ══════════════════════════════════════════════════════════════════════════

@panico_bp.route("/admin/empresas", methods=["GET"])
@_requiere_sistema
def admin_empresas():
    try:
        empresas = list(db["empresas"].find(
            {"activo": True},
            {"razon_social": 1, "nit": 1}
        ).sort("razon_social", 1))
        return ok(serializar(empresas))
    except Exception as e:
        return err(str(e))


@panico_bp.route("/admin/mensajes", methods=["GET"])
@_requiere_sistema
def admin_obtener_mensajes():
    from app.servicios.boton_panico.controller import MSG_DEFAULT_SMS, MSG_DEFAULT_WHATSAPP, MSG_DEFAULT_LLAMADA
    eid = request.args.get("empresa_id", "").strip()
    if not eid:
        return err("empresa_id requerido", 400)
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
        })
    except Exception as e:
        return err(str(e))


@panico_bp.route("/admin/mensajes/<tipo>", methods=["PUT"])
@_requiere_sistema
def admin_guardar_mensaje(tipo):
    from app.servicios.boton_panico.controller import MSG_DEFAULT_SMS, MSG_DEFAULT_WHATSAPP, MSG_DEFAULT_LLAMADA
    CAMPOS = {"llamada": "mensaje_llamada", "sms": "mensaje_sms", "whatsapp": "mensaje_whatsapp"}
    if tipo not in CAMPOS:
        return err("Tipo inválido", 400)
    eid = request.args.get("empresa_id", "").strip()
    if not eid:
        return err("empresa_id requerido", 400)
    datos = request.get_json(silent=True) or {}
    mensaje = str(datos.get("mensaje", "")).strip()
    if not mensaje:
        return err("El mensaje no puede estar vacío", 400)
    try:
        PanicConfigModel.guardar_mensaje_empresa(eid, CAMPOS[tipo], mensaje)
        return ok(mensaje="Mensaje guardado")
    except Exception as e:
        return err(str(e))


@panico_bp.route("/admin/mensajes/<tipo>", methods=["DELETE"])
@_requiere_sistema
def admin_restablecer_mensaje(tipo):
    from app.servicios.boton_panico.controller import MSG_DEFAULT_SMS, MSG_DEFAULT_WHATSAPP, MSG_DEFAULT_LLAMADA
    CAMPOS   = {"llamada": "mensaje_llamada", "sms": "mensaje_sms", "whatsapp": "mensaje_whatsapp"}
    DEFAULTS = {"llamada": MSG_DEFAULT_LLAMADA, "sms": MSG_DEFAULT_SMS, "whatsapp": MSG_DEFAULT_WHATSAPP}
    if tipo not in CAMPOS:
        return err("Tipo inválido", 400)
    eid = request.args.get("empresa_id", "").strip()
    if not eid:
        return err("empresa_id requerido", 400)
    try:
        PanicConfigModel.limpiar_mensaje_empresa(eid, CAMPOS[tipo])
        return ok({"default": DEFAULTS[tipo]}, mensaje="Restablecido al predeterminado")
    except Exception as e:
        return err(str(e))


@panico_bp.route("/admin/contactos", methods=["GET"])
@_requiere_sistema
def admin_contactos():
    eid = request.args.get("empresa_id", "").strip()
    if not eid:
        return err("empresa_id requerido", 400)
    try:
        contactos = list(
            db["directorio_contactos"].find(
                {
                    "empresa_id":                   ObjectId(eid),
                    "activo":                       True,
                    "es_visible_para_administracion": True,
                },
                {
                    "nombre": 1, "cargo_titulo": 1, "bloque": 1,
                    "telefonos": 1, "foto": 1,
                    "es_visible_para_seguridad": 1,
                    "es_visible_para_administracion": 1,
                    "vinculado_al_boton_de_panico": 1,
                },
            ).sort("nombre", 1)
        )
        return ok(serializar(contactos))
    except Exception as e:
        return err(str(e))


@panico_bp.route("/admin/log", methods=["GET"])
@_requiere_sistema
def admin_log():
    eid         = request.args.get("empresa_id", "").strip()
    fecha_ini   = request.args.get("fecha_ini", "").strip()
    fecha_fin   = request.args.get("fecha_fin", "").strip()
    limite      = min(int(request.args.get("limite", 50)), 200)

    if not eid:
        return err("empresa_id requerido", 400)

    filtro = {"empresa_id": ObjectId(eid)}
    try:
        if fecha_ini:
            filtro.setdefault("activado_en", {})["$gte"] = datetime.fromisoformat(fecha_ini).replace(tzinfo=timezone.utc)
        if fecha_fin:
            filtro.setdefault("activado_en", {})["$lte"] = datetime.fromisoformat(fecha_fin).replace(tzinfo=timezone.utc)
    except ValueError:
        return err("Formato de fecha inválido. Use YYYY-MM-DD", 400)

    try:
        eventos = list(
            db["panic_events"]
            .find(filtro)
            .sort("activado_en", -1)
            .limit(limite)
        )
        return ok(serializar(eventos))
    except Exception as e:
        return err(str(e))
