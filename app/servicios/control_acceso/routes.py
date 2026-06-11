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
    tipo_credencial = d.get("tipo_credencial", "unico")
    cred = AccessCredentialModel.crear(
        cid, uid, visitante,
        tipo_credencial=tipo_credencial,
        metodo=d.get("metodo_autenticacion", "QR"),
        configuracion_recurrencia=d.get("configuracion_recurrencia"),
        vigencia_inicio=_fecha((d.get("vigencia") or {}).get("inicio")),
        vigencia_fin=_fecha((d.get("vigencia") or {}).get("fin")),
        unidad=unidad,
    )
    # Notificar al admin si es contratista pendiente
    if cred.get("estado") == "pendiente_aprobacion":
        import threading
        threading.Thread(
            target=AccessController.notificar_admin_nuevo_contratista,
            args=(cred, cid),
            daemon=True
        ).start()
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
    return ok(serializar(AccessLogModel.listar(
        cid,
        limite=int(request.args.get("limite", 50)),
        residente_id=request.args.get("residente_id", ""),
        tipo=request.args.get("tipo", ""),
        fecha=request.args.get("fecha", ""),
    )))


# ── Historial de accesos a mi unidad (residente) ───────────────────────────
@control_acceso_bp.route("/mis-accesos", methods=["GET"])
@requiere_login
def mis_accesos():
    """Devuelve el historial de quién accedió a la unidad del residente activo."""
    cid = _conjunto_efectivo()
    uid = _usuario_id()
    if not cid or not uid:
        return err("Sin sesión válida", 400)
    # Obtener torre/apartamento del residente
    asoc = db["asociaciones"].find_one(
        {"empresa_id": ObjectId(cid), "user_id": ObjectId(uid), "activo": True},
        {"torre": 1, "apartamento": 1}
    ) or {}
    torre = asoc.get("torre", "")
    apto  = asoc.get("apartamento", "")
    logs  = AccessLogModel.listar_por_unidad(
        cid, torre, apto,
        limite=int(request.args.get("limite", 40))
    )
    return ok(serializar(logs))


# ── Dashboard de estadísticas ──────────────────────────────────────────────
@control_acceso_bp.route("/estadisticas", methods=["GET"])
@requiere_login
def estadisticas():
    cid = _conjunto_efectivo()
    if not cid:
        return err("Sin conjunto en sesión", 400)
    return ok(AccessLogModel.estadisticas(cid))


# ══════════════════════════════════════════════════════════════════════════
# FASE 2 — QR real, invitación, aprobación contratistas, Cloudinary, courier
# ══════════════════════════════════════════════════════════════════════════

# ── QR como imagen (base64 PNG) ────────────────────────────────────────────
@control_acceso_bp.route("/credenciales/<cred_id>/qr", methods=["GET"])
@requiere_login
def qr_credencial(cred_id):
    """Devuelve el QR de una credencial como {qr_base64: 'data:image/png;...'}."""
    cred = db["access_credentials"].find_one({"_id": ObjectId(cred_id)})
    if not cred:
        return err("Credencial no encontrada", 404)
    # Solo el solicitante o sistema puede ver el QR
    uid = _usuario_id()
    if not _es_sistema() and str(cred.get("solicitante_id")) != uid:
        return err("Acceso denegado", 403)
    from app.servicios.control_acceso.qr_utils import generar_qr_base64
    codigo = cred.get("codigo", "")
    return ok({"qr_base64": generar_qr_base64(codigo), "codigo": codigo})


# ── Invitación pública (sin login) ─────────────────────────────────────────
@control_acceso_bp.route("/invitacion/<codigo>", methods=["GET"])
def ver_invitacion(codigo):
    """Página pública: el visitante ve su QR + PIN. No requiere login."""
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return "Enlace inválido", 400
    # Busca la credencial por código (sin filtro de conjunto; código es único en el sistema)
    cred = db["access_credentials"].find_one({"codigo": codigo, "estado": "activo"})
    if not cred:
        return render_template("servicios/control_acceso_invitacion_invalida.html")
    from app.servicios.control_acceso.qr_utils import generar_qr_base64
    from app import db as _db
    # Info del conjunto
    cid = cred.get("conjunto_id")
    empresa = _db["empresas"].find_one({"_id": cid}, {"razon_social": 1, "nombre": 1}) or {}
    conjunto_nombre = empresa.get("razon_social") or empresa.get("nombre") or "Conjunto"
    qr_b64 = generar_qr_base64(codigo)
    return render_template(
        "servicios/control_acceso_invitacion.html",
        cred=cred,
        codigo=codigo,
        qr_b64=qr_b64,
        conjunto_nombre=conjunto_nombre,
    )


# ── Enviar invitación WhatsApp al visitante ────────────────────────────────
@control_acceso_bp.route("/credenciales/<cred_id>/enviar-invitacion", methods=["POST"])
@requiere_login
def enviar_invitacion(cred_id):
    """Envía WhatsApp al visitante con el enlace de invitación."""
    cred = db["access_credentials"].find_one({"_id": ObjectId(cred_id)})
    if not cred:
        return err("Credencial no encontrada", 404)
    uid = _usuario_id()
    if not _es_sistema() and str(cred.get("solicitante_id")) != uid:
        return err("Acceso denegado", 403)
    d = request.get_json(silent=True) or {}
    telefono = (d.get("telefono") or cred.get("visitante_telefono") or "").strip()
    if not telefono:
        return err("Número de teléfono requerido", 400)
    # Construir URL pública
    host = request.host_url.rstrip("/")
    enlace = f"{host}/servicios/control_acceso/invitacion/{cred['codigo']}"
    import threading
    threading.Thread(
        target=AccessController._enviar_invitacion_wa,
        args=(telefono, cred, enlace),
        daemon=True
    ).start()
    db["access_credentials"].update_one(
        {"_id": ObjectId(cred_id)},
        {"$set": {"invitacion_enviada": True, "visitante_telefono": telefono}}
    )
    return ok(mensaje="Invitación enviada por WhatsApp")


# ── Aprobación de contratistas ─────────────────────────────────────────────
@control_acceso_bp.route("/credenciales/<cred_id>/aprobar", methods=["POST"])
@requiere_login
def aprobar_credencial(cred_id):
    """Admin/Sistema aprueba la credencial de un contratista."""
    if not _es_sistema():
        rol = session.get("rol", "")
        if "admin" not in rol.lower():
            return err("Acceso denegado", 403)
    from datetime import datetime as dt
    r = db["access_credentials"].update_one(
        {"_id": ObjectId(cred_id), "estado": "pendiente_aprobacion"},
        {"$set": {
            "estado": "activo",
            "aprobacion.aprobado_por": _usuario_id(),
            "aprobacion.aprobado_en": dt.utcnow(),
        }}
    )
    if not r.modified_count:
        return err("Credencial no encontrada o ya procesada", 404)
    # WhatsApp al residente solicitante
    cred = db["access_credentials"].find_one({"_id": ObjectId(cred_id)})
    import threading
    threading.Thread(
        target=AccessController._notificar_aprobacion,
        args=(cred, True, ""),
        daemon=True
    ).start()
    return ok(mensaje="Credencial aprobada")


@control_acceso_bp.route("/credenciales/<cred_id>/rechazar", methods=["POST"])
@requiere_login
def rechazar_credencial(cred_id):
    """Admin/Sistema rechaza la credencial de un contratista."""
    if not _es_sistema():
        rol = session.get("rol", "")
        if "admin" not in rol.lower():
            return err("Acceso denegado", 403)
    from datetime import datetime as dt
    d = request.get_json(silent=True) or {}
    motivo = (d.get("motivo") or "Sin motivo indicado").strip()
    r = db["access_credentials"].update_one(
        {"_id": ObjectId(cred_id), "estado": "pendiente_aprobacion"},
        {"$set": {
            "estado": "rechazado",
            "aprobacion.rechazado_por": _usuario_id(),
            "aprobacion.rechazado_en": dt.utcnow(),
            "aprobacion.motivo": motivo,
        }}
    )
    if not r.modified_count:
        return err("Credencial no encontrada o ya procesada", 404)
    cred = db["access_credentials"].find_one({"_id": ObjectId(cred_id)})
    import threading
    threading.Thread(
        target=AccessController._notificar_aprobacion,
        args=(cred, False, motivo),
        daemon=True
    ).start()
    return ok(mensaje="Credencial rechazada")


@control_acceso_bp.route("/credenciales/pendientes", methods=["GET"])
@requiere_login
def listar_pendientes():
    """Lista de credenciales pendientes de aprobación (admin/sistema)."""
    if not _es_sistema():
        rol = session.get("rol", "")
        if "admin" not in rol.lower():
            return err("Acceso denegado", 403)
    cid = _conjunto_efectivo()
    if not cid:
        return err("empresa_id requerido", 400)
    pendientes = list(db["access_credentials"].find({
        "conjunto_id": ObjectId(cid),
        "estado": "pendiente_aprobacion",
    }).sort("creado_en", -1))
    return ok(serializar(pendientes))


# ── Subida de documentos a Cloudinary ─────────────────────────────────────
@control_acceso_bp.route("/credenciales/<cred_id>/documentos", methods=["POST"])
@requiere_login
def subir_documento(cred_id):
    """Sube un documento a Cloudinary y guarda la URL en la credencial."""
    cred = db["access_credentials"].find_one({"_id": ObjectId(cred_id)})
    if not cred:
        return err("Credencial no encontrada", 404)
    uid = _usuario_id()
    if not _es_sistema() and str(cred.get("solicitante_id")) != uid:
        return err("Acceso denegado", 403)
    if "archivo" not in request.files:
        return err("Campo 'archivo' requerido", 400)
    archivo = request.files["archivo"]
    tipo_doc = (request.form.get("tipo") or "documento").strip()
    try:
        import cloudinary.uploader
        import os
        from flask import current_app
        resultado = cloudinary.uploader.upload(
            archivo,
            folder=f"control_acceso/{cid}/{cred_id}",
            public_id=f"{tipo_doc}_{cred['codigo']}",
            resource_type="auto",
        )
        url = resultado.get("secure_url", "")
        db["access_credentials"].update_one(
            {"_id": ObjectId(cred_id)},
            {"$push": {"documentos": {"tipo": tipo_doc, "url": url,
                                      "subido_en": __import__("datetime").datetime.utcnow()}}}
        )
        return ok({"url": url, "tipo": tipo_doc})
    except Exception as ex:
        log.error("Cloudinary upload error: %s", ex)
        return err(f"Error al subir documento: {ex}", 500)


# ── Flujo Courier (domicilio) ──────────────────────────────────────────────
@control_acceso_bp.route("/courier/registrar", methods=["POST"])
@requiere_login
def registrar_courier():
    """Portería registra un domicilio. Notifica al residente por WhatsApp.
    Si no responde en N minutos, envía recordatorio de que debe bajar."""
    cid = _conjunto_efectivo()
    if not cid:
        return err("Sin conjunto", 400)
    d = request.get_json(silent=True) or {}
    nombre_courier  = (d.get("nombre_courier") or "Mensajero").strip()
    empresa_courier = (d.get("empresa") or "").strip()
    unidad = d.get("unidad") or {}
    if not unidad:
        return err("Unidad del residente requerida", 400)
    # Buscar teléfono del residente
    asoc = db["asociaciones"].find_one({
        "empresa_id": ObjectId(cid), "activo": True,
        "torre": unidad.get("torre", ""),
        "apartamento": unidad.get("apartamento", ""),
    }) or {}
    res_uid = asoc.get("user_id")
    telefono_residente = ""
    nombre_residente = "Residente"
    if res_uid:
        u = db["users"].find_one({"_id": res_uid}, {"telefono": 1, "nombre": 1, "apellido": 1}) or {}
        telefono_residente = u.get("telefono", "")
        nombre_residente = f"{u.get('nombre','')} {u.get('apellido','')}".strip()
    # Registrar log de courier
    log_id = AccessLogModel.registrar(
        cid,
        visitante={"nombre": nombre_courier, "empresa": empresa_courier, "tipo": "domicilio"},
        unidad=unidad,
        metodo="COURIER",
        estado="courier_esperando",
        vigilante_id=_usuario_id(),
        detalle=f"Domicilio de {empresa_courier or nombre_courier}",
    )
    if telefono_residente:
        import threading
        cfg = CaConfigModel.obtener(cid)
        timeout_min = cfg.get("courier", {}).get("timeout_minutos", 5)
        threading.Thread(
            target=AccessController._flujo_courier,
            args=(cid, log_id, telefono_residente, nombre_residente,
                  nombre_courier, empresa_courier, unidad, timeout_min),
            daemon=True
        ).start()
    return ok({"log_id": log_id, "mensaje": "Residente notificado"}, status=201)
