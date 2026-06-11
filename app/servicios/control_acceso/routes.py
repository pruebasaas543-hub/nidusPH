"""
app/servicios/control_acceso/routes.py
───────────────────────────────────────
API REST del módulo Control de Acceso. Prefijo: /servicios/control_acceso

Endpoints de Twilio (citofonía) son públicos (los llama Twilio), igual que el
webhook del botón de pánico. El resto requiere login.
"""

import logging
from flask import Blueprint, request, session, jsonify, Response, render_template

from app import db
from bson import ObjectId
from app.configuracion.utils import requiere_login, ok, err, serializar
from app.servicios.control_acceso.controller import AccessController
from app.servicios.control_acceso.model import (
    AccessCredentialModel, AccessLogModel, CoaccionModel,
)
from app.servicios.control_acceso.config_model import CaConfigModel, CaBlacklistModel

log = logging.getLogger(__name__)
control_acceso_bp = Blueprint("control_acceso", __name__,
                              url_prefix="/servicios/control_acceso")


def _conjunto_id():  return session.get("empresa_id", "")
def _usuario_id():   return session.get("usuario_id", "")


def _es_sistema():
    from app.configuracion.roles.model import RolModel
    return session.get("rol", "") in RolModel.nombres_sistema()


def _conjunto_efectivo():
    """Conjunto a usar. Sistema → el SELECCIONADO (?empresa_id= o body), o el de
    sesión. Usuario normal → siempre el de su sesión. (Mismo patrón que pánico.)"""
    if _es_sistema():
        eid = (request.args.get("empresa_id") or "").strip()
        if not eid:
            d = request.get_json(silent=True) or {}
            eid = (d.get("empresa_id") or "").strip()
        return eid or session.get("empresa_id", "")
    return session.get("empresa_id", "")


def _conjunto_info(cid: str):
    if not cid:
        return "", ""
    e = db["empresas"].find_one({"_id": ObjectId(cid)},
                                {"razon_social": 1, "nombre": 1, "direccion": 1}) or {}
    return (e.get("razon_social") or e.get("nombre") or ""), (e.get("direccion") or "")


# ── Conjuntos disponibles (selector del SuperAdmin) ────────────────────────
@control_acceso_bp.route("/conjuntos", methods=["GET"])
@requiere_login
def listar_conjuntos():
    """Lista de conjuntos/empresas para el selector. Solo para sistema."""
    if not _es_sistema():
        return ok([])
    empresas = list(db["empresas"].find({}, {"razon_social": 1, "nombre": 1})
                    .sort("razon_social", 1))
    return ok(serializar(empresas))


# ── Portería: validar código (QR / PIN 6 chars / coacción) ─────────────────
@control_acceso_bp.route("/validar", methods=["POST"])
@requiere_login
def validar():
    cid = _conjunto_efectivo()
    if not cid:
        return err("Sin conjunto en sesión", 400)
    datos  = request.get_json(silent=True) or {}
    codigo = (datos.get("codigo") or "").strip()
    if not codigo:
        return err("Código requerido", 400)
    nombre, direccion = _conjunto_info(cid)
    resultado = AccessController.validar_acceso(
        cid, codigo, vigilante_id=_usuario_id(),
        conjunto_nombre=nombre, conjunto_direccion=direccion)
    return ok(resultado)


# ── Portería: ingreso manual rápido (Nombre, Documento, Unidad) ────────────
@control_acceso_bp.route("/ingreso-manual", methods=["POST"])
@requiere_login
def ingreso_manual():
    cid = _conjunto_efectivo()
    if not cid:
        return err("Sin conjunto en sesión", 400)
    d = request.get_json(silent=True) or {}
    nombre    = (d.get("nombre") or "").strip()
    documento = (d.get("documento") or "").strip()
    unidad    = d.get("unidad") or {}
    if not nombre or not documento or not unidad:
        return err("Nombre, documento y unidad son obligatorios", 400)
    res = AccessController.ingreso_manual(cid, nombre, documento, unidad,
                                          vigilante_id=_usuario_id())
    return ok(res)


# ── Citofonía: iniciar llamada al residente ────────────────────────────────
@control_acceso_bp.route("/citofonia/llamar", methods=["POST"])
@requiere_login
def citofonia_llamar():
    cid = _conjunto_efectivo()
    if not cid:
        return err("Sin conjunto en sesión", 400)
    d = request.get_json(silent=True) or {}
    log_id  = (d.get("log_id") or "").strip()
    numero  = (d.get("numero") or "").strip()
    visita  = (d.get("nombre_visita") or "").strip()
    if not log_id or not numero:
        return err("log_id y número del residente requeridos", 400)
    res = AccessController.iniciar_citofonia(cid, log_id, numero, visita)
    if not res.get("ok"):
        return err(res.get("error", "No se pudo iniciar la llamada"))
    return ok(res)


# ── Citofonía: TwiML (PÚBLICO, lo pide Twilio) ─────────────────────────────
@control_acceso_bp.route("/citofonia/twiml", methods=["GET", "POST"])
def citofonia_twiml():
    log_id = request.values.get("log_id", "")
    visita = request.values.get("visita", "")
    xml = AccessController.twiml_citofonia(log_id, visita)
    return Response(xml, mimetype="text/xml")


# ── Citofonía: callback DTMF (PÚBLICO, lo llama Twilio con la tecla) ────────
@control_acceso_bp.route("/citofonia/callback", methods=["POST"])
def citofonia_callback():
    log_id = request.values.get("log_id", "")
    digito = (request.values.get("Digits") or "").strip()
    xml = AccessController.procesar_dtmf(log_id, digito)
    return Response(xml, mimetype="text/xml")


# ── Citofonía: estado del log (la portería hace polling) ───────────────────
@control_acceso_bp.route("/citofonia/estado/<log_id>", methods=["GET"])
@requiere_login
def citofonia_estado(log_id):
    doc = AccessLogModel.obtener(log_id)
    if not doc:
        return err("Log no encontrado", 404)
    return ok({"estado": doc.get("estado", ""), "detalle": doc.get("detalle", "")})


# ── Monitoreo: coacciones activas (polling del panel rojo) ─────────────────
@control_acceso_bp.route("/coacciones-activas", methods=["GET"])
@requiere_login
def coacciones_activas():
    cid = _conjunto_efectivo()
    if not cid:
        return ok([])
    return ok(serializar(AccessLogModel.coacciones_activas(cid)))


@control_acceso_bp.route("/coaccion/atender", methods=["POST"])
@requiere_login
def atender_coaccion():
    from datetime import datetime
    d = request.get_json(silent=True) or {}
    log_id = (d.get("log_id") or "").strip()
    if not log_id:
        return err("log_id requerido", 400)
    r = db["access_logs"].update_one(
        {"_id": ObjectId(log_id)},
        {"$set": {"coaccion_activa": False, "estado": "coaccion_atendida",
                  "atendido_por": _usuario_id(), "atendido_en": datetime.utcnow()}})
    return ok(mensaje="Atendida") if r.modified_count else err("No encontrada", 404)


# ── Credenciales (residente: crear QR/PIN, listar, revocar) ────────────────
@control_acceso_bp.route("/credenciales", methods=["POST"])
@requiere_login
def crear_credencial():
    cid = _conjunto_efectivo()
    uid = _usuario_id()
    if not cid or not uid:
        return err("Sin conjunto o usuario en sesión", 400)
    d = request.get_json(silent=True) or {}
    visitante = d.get("visitante") or {}
    if not visitante.get("nombre"):
        return err("Nombre del visitante requerido", 400)
    # Unidad: si no viene, se deriva de la asociación del residente (torre/apto)
    unidad = d.get("unidad") or {}
    if not unidad:
        a = db["asociaciones"].find_one({"user_id": ObjectId(uid), "empresa_id": ObjectId(cid)}) or {}
        unidad = {"torre": a.get("torre", ""), "apartamento": a.get("apartamento", ""),
                  "bloque": a.get("unidad", "")}
    from datetime import datetime
    def _fecha(v):
        try:
            return datetime.fromisoformat(v) if v else None
        except Exception:
            return None
    cred = AccessCredentialModel.crear(
        cid, uid, visitante,
        tipo_credencial=d.get("tipo_credencial", "unico"),
        metodo=d.get("metodo_autenticacion", "QR"),
        configuracion_recurrencia=d.get("configuracion_recurrencia"),
        vigencia_inicio=_fecha((d.get("vigencia") or {}).get("inicio")),
        vigencia_fin=_fecha((d.get("vigencia") or {}).get("fin")),
        unidad=unidad,
    )
    return ok(serializar(cred), status=201)


@control_acceso_bp.route("/credenciales", methods=["GET"])
@requiere_login
def listar_credenciales():
    cid = _conjunto_efectivo()
    if not cid:
        return err("Sin conjunto", 400)
    # Sistema → todas las del conjunto; residente → solo las suyas
    if _es_sistema():
        return ok(serializar(AccessCredentialModel.listar_por_conjunto(cid)))
    uid = _usuario_id()
    if not uid:
        return err("Sin usuario en sesión", 400)
    return ok(serializar(AccessCredentialModel.listar_por_solicitante(cid, uid)))


@control_acceso_bp.route("/credenciales/<cred_id>", methods=["DELETE"])
@requiere_login
def revocar_credencial(cred_id):
    return ok(mensaje="Revocada") if AccessCredentialModel.revocar(cred_id) else err("No encontrada", 404)


# ── PIN de coacción (residente lo configura/cambia) ────────────────────────
@control_acceso_bp.route("/mi-pin-coaccion", methods=["PUT"])
@requiere_login
def set_pin_coaccion():
    uid = _usuario_id()
    if not uid:
        return err("Sin usuario en sesión", 400)
    d = request.get_json(silent=True) or {}
    pin = (d.get("pin") or "").strip()
    if not pin or len(pin) < 4:
        return err("El PIN de coacción debe tener al menos 4 caracteres", 400)
    return ok(mensaje="PIN de coacción guardado") if CoaccionModel.set_pin(uid, pin) else err("No se pudo guardar")


# ══════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN GLOBAL (solo es_sistema)
# ══════════════════════════════════════════════════════════════════════════

@control_acceso_bp.route("/config", methods=["GET"])
@requiere_login
def get_config():
    if not _es_sistema():
        return err("Acceso denegado", 403)
    cid = _conjunto_efectivo()
    if not cid:
        return err("empresa_id requerido", 400)
    return ok(serializar(CaConfigModel.obtener(cid)))


@control_acceso_bp.route("/config", methods=["POST"])
@requiere_login
def guardar_config():
    if not _es_sistema():
        return err("Acceso denegado", 403)
    cid = _conjunto_efectivo()
    if not cid:
        return err("empresa_id requerido", 400)
    datos = request.get_json(silent=True) or {}
    datos.pop("empresa_id", None)
    CaConfigModel.guardar(cid, datos)
    return ok(mensaje="Configuración guardada")


@control_acceso_bp.route("/lockdown", methods=["POST"])
@requiere_login
def toggle_lockdown():
    if not _es_sistema():
        # Admin PH también puede activar lockdown
        rol = session.get("rol", "")
        if "admin" not in rol.lower():
            return err("Acceso denegado", 403)
    cid = _conjunto_efectivo()
    if not cid:
        return err("empresa_id requerido", 400)
    d = request.get_json(silent=True) or {}
    activar = bool(d.get("activar", True))
    CaConfigModel.activar_lockdown(cid, _usuario_id(), activar)
    if activar:
        # Notificaciones de emergencia en segundo plano
        import threading
        threading.Thread(
            target=AccessController.notificar_lockdown,
            args=(cid,), daemon=True
        ).start()
    estado = "activado" if activar else "desactivado"
    return ok(mensaje=f"Lockdown {estado}")


# ── Blacklist ──────────────────────────────────────────────────────────────

@control_acceso_bp.route("/blacklist", methods=["GET"])
@requiere_login
def listar_blacklist():
    if not _es_sistema():
        return err("Acceso denegado", 403)
    cid = _conjunto_efectivo()
    if not cid:
        return err("empresa_id requerido", 400)
    return ok(serializar(CaBlacklistModel.listar(cid)))


@control_acceso_bp.route("/blacklist", methods=["POST"])
@requiere_login
def agregar_blacklist():
    if not _es_sistema():
        return err("Acceso denegado", 403)
    cid = _conjunto_efectivo()
    if not cid:
        return err("empresa_id requerido", 400)
    d = request.get_json(silent=True) or {}
    documento = (d.get("documento") or "").strip()
    nombre    = (d.get("nombre") or "").strip()
    if not documento or not nombre:
        return err("Documento y nombre son obligatorios", 400)
    bid = CaBlacklistModel.agregar(cid, documento, nombre,
                                   motivo=d.get("motivo", ""),
                                   bloqueado_por=_usuario_id())
    return ok({"id": bid}, status=201)


@control_acceso_bp.route("/blacklist/<bid>", methods=["DELETE"])
@requiere_login
def eliminar_blacklist(bid):
    if not _es_sistema():
        return err("Acceso denegado", 403)
    return ok(mensaje="Eliminado") if CaBlacklistModel.desactivar(bid) else err("No encontrado", 404)


# ── Búsqueda express de residentes (sin foto) ──────────────────────────────

@control_acceso_bp.route("/residentes/buscar", methods=["GET"])
@requiere_login
def buscar_residente():
    cid = _conjunto_efectivo()
    if not cid:
        return err("Sin conjunto", 400)
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return err("Mínimo 2 caracteres", 400)
    # Busca en asociaciones del conjunto y cruza con users
    asocs = list(db["asociaciones"].find({
        "empresa_id": ObjectId(cid), "activo": True
    }))
    resultados = []
    for a in asocs:
        uid = a.get("user_id")
        if not uid:
            continue
        u = db["users"].find_one(
            {"_id": uid},
            # Sin foto, sin password, sin pin_coaccion — privacidad
            {"nombre": 1, "apellido": 1, "email": 1, "vehiculos": 1}
        ) or {}
        nombre_completo = f"{u.get('nombre','')} {u.get('apellido','')}".strip()
        unidad = f"Torre {a.get('torre','')} - {a.get('apartamento','')}".strip("- ")
        if (q.lower() in nombre_completo.lower() or
                q.lower() in unidad.lower() or
                q.lower() in (a.get("apartamento") or "").lower()):
            resultados.append({
                "nombre":     nombre_completo,
                "unidad":     unidad,
                "torre":      a.get("torre", ""),
                "apartamento": a.get("apartamento", ""),
                "vehiculos":  u.get("vehiculos", []),
            })
        if len(resultados) >= 10:
            break
    return ok(resultados)


# ── Estado de lockdown (para que portería pueda saber si está activo) ──────

@control_acceso_bp.route("/lockdown/estado", methods=["GET"])
@requiere_login
def estado_lockdown():
    cid = _conjunto_efectivo()
    if not cid:
        return ok({"activo": False})
    return ok({"activo": CaConfigModel.lockdown_activo(cid)})


# ── Bitácora / minuta ──────────────────────────────────────────────────────
@control_acceso_bp.route("/logs", methods=["GET"])
@requiere_login
def listar_logs():
    cid = _conjunto_efectivo()
    if not cid:
        return err("Sin conjunto en sesión", 400)
    return ok(serializar(AccessLogModel.listar(cid, limite=int(request.args.get("limite", 50)))))
