"""
app/servicios/control_acceso/routes.py
───────────────────────────────────────
API REST del módulo Control de Acceso. Prefijo: /servicios/control_acceso

Endpoints de Twilio (citofonía) son públicos (los llama Twilio), igual que el
webhook del botón de pánico. El resto requiere login.
"""

import logging
from flask import Blueprint, request, session, jsonify, Response

from app import db
from bson import ObjectId
from app.configuracion.utils import requiere_login, ok, err, serializar
from app.servicios.control_acceso.controller import AccessController
from app.servicios.control_acceso.model import (
    AccessCredentialModel, AccessLogModel, CoaccionModel,
)

log = logging.getLogger(__name__)
control_acceso_bp = Blueprint("control_acceso", __name__,
                              url_prefix="/servicios/control_acceso")


def _conjunto_id():  return session.get("empresa_id", "")
def _usuario_id():   return session.get("usuario_id", "")


def _conjunto_info(cid: str):
    if not cid:
        return "", ""
    e = db["empresas"].find_one({"_id": ObjectId(cid)},
                                {"razon_social": 1, "nombre": 1, "direccion": 1}) or {}
    return (e.get("razon_social") or e.get("nombre") or ""), (e.get("direccion") or "")


# ── Portería: validar código (QR / PIN 6 chars / coacción) ─────────────────
@control_acceso_bp.route("/validar", methods=["POST"])
@requiere_login
def validar():
    cid = _conjunto_id()
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
    cid = _conjunto_id()
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
    cid = _conjunto_id()
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
    cid = _conjunto_id()
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
    cid = _conjunto_id()
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
    cid = _conjunto_id()
    uid = _usuario_id()
    if not cid or not uid:
        return err("Sin conjunto o usuario en sesión", 400)
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


# ── Bitácora / minuta ──────────────────────────────────────────────────────
@control_acceso_bp.route("/logs", methods=["GET"])
@requiere_login
def listar_logs():
    cid = _conjunto_id()
    if not cid:
        return err("Sin conjunto en sesión", 400)
    return ok(serializar(AccessLogModel.listar(cid, limite=int(request.args.get("limite", 50)))))
