"""
app/servicios/boton_panico/routes.py
API REST del módulo Botón de Pánico.
Prefijo: /servicios/boton_panico
"""

from flask import Blueprint, request, session, jsonify
from bson import ObjectId
from datetime import datetime, timezone
import logging

from app import db
from app.configuracion.utils import requiere_login, ok, err, serializar
from app.configuracion.roles.model import RolModel
from app.servicios.boton_panico.controller import PanicController
from app.servicios.boton_panico.model import (
    PanicConfigModel, PanicEventModel, UserPanicContactModel, NotificationStateModel,
    MAPA_ESTADOS, JERARQUIA_ESTADOS, ESTADOS_PENDIENTES, ESTADOS_FINALES
)

log = logging.getLogger(__name__)

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


def _empresa_admin() -> str:
    """Empresa para vistas config/log.
    Sistema: query param empresa_id. Normal: empresa de sesión.
    """
    if _es_sistema():
        return request.args.get("empresa_id", "").strip()
    return _empresa_id()


def _eid_efectivo() -> str:
    """Empresa para la pestaña Emergencia.
    Sistema: query param empresa_id (preferido) o empresa de sesión.
    Normal: empresa de sesión únicamente.
    """
    if not _es_sistema():
        return _empresa_id()
    return request.args.get("empresa_id", "").strip() or _empresa_id()


def _tiene_permiso(accion: str) -> bool:
    """True si el usuario puede ejecutar la acción del botón de pánico.

    El usuario del sistema siempre puede. Para el resto se consulta permisos_rol.
    """
    if _es_sistema():
        return True
    from app.servicios.permisos.model import PermisosRolModel
    perms = PermisosRolModel.obtener_para_sesion(_empresa_id(), session.get("rol", ""), "boton_panico")
    return bool(perms.get(accion))


def _requiere_permiso(accion: str):
    """Decorador: exige permiso de botón de pánico para la acción dada."""
    from functools import wraps
    from flask import jsonify
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("num_doc"):
                return jsonify({"ok": False, "error": "No autenticado"}), 401
            if not _tiene_permiso(accion):
                return jsonify({"ok": False, "error": "Sin permisos"}), 403
            return f(*args, **kwargs)
        return decorated
    return wrapper


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
    eid = _eid_efectivo()
    if not eid:
        return err("No hay empresa en sesión", 400)
    _, cfg = PanicController.obtener_config(eid)
    return ok(serializar(cfg))


@panico_bp.route("/config", methods=["PUT"])
@requiere_login
@_requiere_permiso("emergencia")
def guardar_config():
    eid = _eid_efectivo()
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
    try:
        if _es_sistema():
            eid = _eid_efectivo()
            match = {"vinculado_al_boton_de_panico": True, "activo": True}
            if eid:
                match["empresa_id"] = ObjectId(eid)
            pipeline = [
                {"$match": match},
                {"$lookup": {
                    "from": "empresas",
                    "localField": "empresa_id",
                    "foreignField": "_id",
                    "as": "_emp",
                }},
                {"$unwind": {"path": "$_emp", "preserveNullAndEmptyArrays": True}},
                {"$project": {
                    "nombre": 1, "cargo_titulo": 1, "bloque": 1,
                    "telefonos": 1, "empresa_id": 1, "foto_data": 1,
                    "empresa_nombre": {"$ifNull": ["$_emp.razon_social", "Sin nombre"]},
                }},
                {"$sort": {"empresa_nombre": 1, "nombre": 1}},
            ]
            docs = list(db["directorio_contactos"].aggregate(pipeline))
        else:
            eid = _eid_efectivo()
            if not eid:
                return err("No hay empresa en sesión", 400)
            docs = list(
                db["directorio_contactos"].find(
                    {"empresa_id": ObjectId(eid), "vinculado_al_boton_de_panico": True},
                    {"nombre": 1, "cargo_titulo": 1, "bloque": 1, "telefonos": 1, "foto_data": 1},
                ).sort("nombre", 1)
            )
        resultado = []
        for doc in docs:
            d = serializar(doc)
            d["tiene_foto"] = bool(doc.get("foto_data"))
            d.pop("foto_data", None)
            resultado.append(d)
        return ok(resultado)
    except Exception as e:
        return err(str(e))


# ── Activar pánico ────────────────────────────────────────────────────────

@panico_bp.route("/trigger", methods=["POST"])
@requiere_login
@_requiere_permiso("emergencia")
def trigger():
    eid = _eid_efectivo()
    if not eid:
        return err("No hay empresa en sesión", 400)

    uid = session.get("usuario_id")
    torre = ""
    apartamento = ""
    try:
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
        eid, uid, _nombre_res(), _nombre_empresa(),
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
    if _es_sistema():
        # Superadmin: últimas activaciones de todas las empresas
        try:
            eventos = list(
                db["panic_events"]
                .find({}, {"activado_en": 1, "empresa_id": 1, "residente_id": 1,
                           "nombre_residente": 1, "resultado": 1})
                .sort("activado_en", -1)
                .limit(20)
            )
            return ok(serializar(eventos))
        except Exception as e:
            return err(str(e))
    eid = _eid_efectivo()
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
@requiere_login
@_requiere_permiso("configuracion")
def admin_obtener_mensajes():
    from app.servicios.boton_panico.controller import MSG_DEFAULT_SMS, MSG_DEFAULT_WHATSAPP, MSG_DEFAULT_LLAMADA
    eid = _empresa_admin()
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
@requiere_login
@_requiere_permiso("configuracion")
def admin_guardar_mensaje(tipo):
    from app.servicios.boton_panico.controller import MSG_DEFAULT_SMS, MSG_DEFAULT_WHATSAPP, MSG_DEFAULT_LLAMADA
    CAMPOS = {"llamada": "mensaje_llamada", "sms": "mensaje_sms", "whatsapp": "mensaje_whatsapp"}
    if tipo not in CAMPOS:
        return err("Tipo inválido", 400)
    eid = _empresa_admin()
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
@requiere_login
@_requiere_permiso("configuracion")
def admin_restablecer_mensaje(tipo):
    from app.servicios.boton_panico.controller import MSG_DEFAULT_SMS, MSG_DEFAULT_WHATSAPP, MSG_DEFAULT_LLAMADA
    CAMPOS   = {"llamada": "mensaje_llamada", "sms": "mensaje_sms", "whatsapp": "mensaje_whatsapp"}
    DEFAULTS = {"llamada": MSG_DEFAULT_LLAMADA, "sms": MSG_DEFAULT_SMS, "whatsapp": MSG_DEFAULT_WHATSAPP}
    if tipo not in CAMPOS:
        return err("Tipo inválido", 400)
    eid = _empresa_admin()
    if not eid:
        return err("empresa_id requerido", 400)
    try:
        PanicConfigModel.limpiar_mensaje_empresa(eid, CAMPOS[tipo])
        return ok({"default": DEFAULTS[tipo]}, mensaje="Restablecido al predeterminado")
    except Exception as e:
        return err(str(e))


@panico_bp.route("/admin/contactos", methods=["GET"])
@requiere_login
@_requiere_permiso("configuracion")
def admin_contactos():
    eid = _empresa_admin()
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




@panico_bp.route("/jerarquia-estados", methods=["GET"])
@requiere_login
def jerarquia_estados():
    """Devuelve la jerarquía de estados por canal para uso en frontend."""
    from flask import jsonify as _j
    return _j({"ok": True, "data": JERARQUIA_ESTADOS})


@panico_bp.route("/admin/refresh-lote", methods=["POST"])
@requiere_login
@_requiere_permiso("log")
def admin_refresh_lote():
    """OBSOLETO: los webhooks de Twilio actualizan los estados en tiempo real.

    Antes este endpoint reconsultaba Twilio y reescribía el `resultado` completo,
    lo que pisaba la traza que los webhooks escriben en vivo (condición de carrera).
    Ahora es un no-op: el frontend solo re-lee el log para mostrar lo que ya está en BD.
    """
    from flask import jsonify as _j
    return _j({"ok": True, "actualizados": 0})


@panico_bp.route("/admin/log", methods=["GET"])
@requiere_login
@_requiere_permiso("log")
def admin_log():
    eid         = _empresa_admin()
    fecha_ini   = request.args.get("fecha_ini", "").strip()
    fecha_fin   = request.args.get("fecha_fin", "").strip()
    nombre_res  = request.args.get("nombre_res", "").strip()
    canal_fil   = request.args.get("canal", "").strip()  # NO convertir a lower() aquí
    estado_fil  = request.args.get("estado", "").strip()  # NO convertir a lower() aquí
    pagina      = max(1, int(request.args.get("pagina", 1)))
    por_pagina  = 30

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

    if nombre_res:
        filtro["nombre_residente"] = {"$regex": nombre_res, "$options": "i"}

    # Filtros de canal y estado requieren inspeccionar el resultado
    try:
        cursor = db["panic_events"].find(filtro).sort("activado_en", -1)
        todos  = list(cursor)

        # Post-filtro por canal / estado (están anidados en resultado.externos/directorio)
        if canal_fil or estado_fil:
            filtrados = []
            # Obtener estados válidos para el canal si se especificó
            estados_validos_canal = _obtener_estados_canal(canal_fil) if canal_fil else None

            for ev in todos:
                res = ev.get("resultado", {})

                # Si es evento bloqueado (cooldown), incluir si filtra por error
                if res.get("bloqueado") == True:
                    if not estado_fil or estado_fil.lower() == "error":
                        filtrados.append(ev)
                    continue

                # Para eventos normales: revisar si hay al menos un contacto/canal que coincida
                externos = res.get("externos", [])
                directorio = res.get("directorio", [])
                todos_contactos = externos + directorio

                evento_coincide = False
                for contacto in todos_contactos:
                    canales = contacto.get("canales", {})
                    for tipo_canal, info_canal in canales.items():
                        # Verificar canal
                        if canal_fil and tipo_canal.lower() != canal_fil.lower():
                            continue  # Este canal no coincide, próximo

                        estado_actual = info_canal.get("estado", "")

                        # Validar que el estado sea válido para el canal seleccionado
                        if canal_fil and estados_validos_canal and estado_actual not in estados_validos_canal:
                            continue  # Estado no válido para este canal, próximo

                        # Verificar estado (si hay filtro)
                        if estado_fil and not _estado_coincide(estado_actual, estado_fil):
                            continue  # Este estado no coincide, próximo

                        # Ambos coinciden (o no hay filtro para ellos)
                        evento_coincide = True
                        break
                    if evento_coincide:
                        break

                if evento_coincide:
                    filtrados.append(ev)

            todos = filtrados

        total   = len(todos)
        skip    = (pagina - 1) * por_pagina
        pagina_data = todos[skip: skip + por_pagina]
        # Migración lazy: mapear estados Twilio → internos
        pagina_data = [_migrar_evento_lazy(ev) for ev in pagina_data]

        # Obtener estados válidos por canal para el frontend
        estados_por_canal = {
            "sms": _obtener_estados_canal("sms"),
            "whatsapp": _obtener_estados_canal("whatsapp"),
            "llamada": _obtener_estados_canal("llamada"),
        }

        from flask import jsonify
        return jsonify({
            "ok": True,
            "data": serializar(pagina_data),
            "total": total,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "total_paginas": max(1, -(-total // por_pagina)),
            "estados_por_canal": estados_por_canal,
        })
    except Exception as e:
        return err(str(e))


def _normalizar_estado(estado: str) -> str:
    """Normaliza estados a categorías simples (ok, error, mock)."""
    e = (estado or "").lower()
    # Mapear estado de Twilio al estado interno primero
    estado_interno = MAPA_ESTADOS.get(e, e)
    if estado_interno in ("entregado", "leido", "completado", "recibido", "en_llamada"):
        return "ok"
    if estado_interno == "mock":
        return "mock"
    return "error"

def _estado_coincide(estado_real: str, filtro: str) -> bool:
    """Verifica si un estado real coincide con el filtro (puede ser específico o normalizado)."""
    if not filtro:  # Si no hay filtro, todo coincide
        return True

    e_real = (estado_real or "").lower()
    e_filt = (filtro or "").lower()

    # Coincidencia exacta: "sent" == "sent", "error" == "error", etc
    if e_real == e_filt:
        return True

    # Coincidencia normalizada: "sent" normaliza a "ok", filtro es "ok"
    estado_normalizado = _normalizar_estado(estado_real)
    if estado_normalizado == e_filt:
        return True

    return False


def _obtener_estados_canal(canal: str) -> list:
    """Obtiene todos los estados válidos para un canal desde la BD.

    Args:
        canal: "sms", "whatsapp" o "llamada"

    Returns:
        Lista de nombres en español de los estados válidos
    """
    estados_docs = NotificationStateModel.obtener_estados_por_tipo(canal)
    # Varios estados Twilio pueden mapear al mismo nombre en español
    # (ej. queued e initiated → en_cola). Devolver sin duplicados, conservando el orden.
    nombres = [doc.get("nombreEspanol") for doc in estados_docs]
    return list(dict.fromkeys(nombres))


def _enriquecer_evento_con_transiciones(evento: dict) -> dict:
    """Enriquece un evento con transiciones reales del poller desde twilio_requests_log.

    Busca los logs de Twilio para cada SID y convierte las transiciones_estado
    al formato de historial esperado por el frontend.
    """
    try:
        resultado = evento.get("resultado", {})
        todos_contactos = (resultado.get("externos", []) or []) + (resultado.get("directorio", []) or [])

        for contacto in todos_contactos:
            canales = contacto.get("canales", {})
            for tipo_canal, info_canal in canales.items():
                sid = info_canal.get("sid", "")
                if not sid:
                    continue

                # Buscar el log de Twilio para este SID
                twilio_log = db["twilio_requests_log"].find_one(
                    {"respuesta_inicial.sid": sid, "tipo_notificacion": tipo_canal}
                )

                if twilio_log and twilio_log.get("transiciones_estado"):
                    # Convertir transiciones al formato historial
                    transiciones = twilio_log.get("transiciones_estado", [])
                    historial = []

                    for trans in transiciones:
                        estado_nombre = trans.get("estado", "")
                        timestamp = trans.get("timestamp", "")
                        detalles = trans.get("detalles", "")

                        historial_entry = {
                            "estado": estado_nombre,
                            "en": timestamp,
                        }
                        if detalles:
                            historial_entry["detalle"] = detalles

                        historial.append(historial_entry)

                    # Reemplazar el historial con las transiciones reales
                    if historial:
                        info_canal["historial"] = historial

        return evento
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Error enriqueciendo evento: %s", e)
        return evento


def _migrar_evento_lazy(evento: dict) -> dict:
    """Migración lazy: mapea estados Twilio → estados internos en un evento."""
    resultado = evento.get("resultado", {})

    # Migrar contactos externos y directorio
    for grupo in ("externos", "directorio"):
        for contacto in resultado.get(grupo, []):
            for tipo, info in contacto.get("canales", {}).items():
                # Mapear estado principal - obtener desde BD en lugar de mapeo hardcodeado
                estado_raw = info.get("estado", "")
                if estado_raw and estado_raw not in ESTADOS_FINALES and estado_raw not in ESTADOS_PENDIENTES:
                    info["estado"] = NotificationStateModel.obtener_nombre_espanol(tipo, estado_raw.lower())

                # Mapear estados en historial
                for h in info.get("historial", []):
                    estado_h = h.get("estado", "")
                    if estado_h and estado_h not in ESTADOS_FINALES and estado_h not in ESTADOS_PENDIENTES:
                        h["estado"] = NotificationStateModel.obtener_nombre_espanol(tipo, estado_h.lower())

    return evento


@panico_bp.route("/admin/refresh-estados", methods=["POST"])
@requiere_login
@_requiere_permiso("log")
def admin_refresh_estados():
    """OBSOLETO: los webhooks de Twilio actualizan los estados en tiempo real.

    Antes reconsultaba Twilio y reescribía el `resultado` completo, pisando la
    traza que escriben los webhooks. Ahora solo devuelve el estado actual en BD
    (sin reconsultar Twilio ni reescribir), para que el frontend lo muestre.
    """
    datos     = request.get_json(silent=True) or {}
    evento_id = datos.get("evento_id", "").strip()
    if not evento_id:
        return err("evento_id requerido", 400)
    try:
        from bson import ObjectId as OID
        ev = db["panic_events"].find_one({"_id": OID(evento_id)})
        if not ev:
            return err("Evento no encontrado", 404)

        from flask import jsonify as _jsonify
        return _jsonify({"ok": True, "data": serializar(ev.get("resultado", {})), "actualizado": False})
    except Exception as e:
        return err(str(e))


@panico_bp.route("/admin/buscar-usuario", methods=["GET"])
@_requiere_sistema
def admin_buscar_usuario():
    """Busca usuarios de una empresa por nombre/apellidos o número de documento."""
    q          = request.args.get("q", "").strip()
    empresa_id = request.args.get("empresa_id", "").strip()
    if len(q) < 2:
        return ok([])
    if not empresa_id:
        return err("Debe indicar empresa_id", 400)
    try:
        # 1) IDs de usuarios que pertenecen a esa empresa
        asocs = list(db["asociaciones"].find(
            {"empresa_id": ObjectId(empresa_id), "activo": True},
            {"user_id": 1},
        ))
        user_ids = [a["user_id"] for a in asocs if a.get("user_id")]
        if not user_ids:
            return ok([])

        # 2) Filtrar por texto dentro de esos usuarios
        filtro = {
            "_id": {"$in": user_ids},
            "$or": [
                {"numero_documento": {"$regex": f"^{q}", "$options": "i"}},
                {"nombres":          {"$regex": q, "$options": "i"}},
                {"apellidos":        {"$regex": q, "$options": "i"}},
            ],
        }
        usuarios = list(db["users"].find(
            filtro,
            {"nombres": 1, "apellidos": 1, "numero_documento": 1, "tipo_documento": 1},
        ).limit(15))

        # Datos de empresa
        emp_doc = db["empresas"].find_one({"_id": ObjectId(empresa_id)}, {"razon_social": 1})
        emp_nombre = (emp_doc or {}).get("razon_social", empresa_id)

        resultado = []
        for u in usuarios:
            uid = str(u["_id"])
            nombre_completo = f"{u.get('nombres','')} {u.get('apellidos','')}".strip()
            num_doc = u.get("numero_documento", "")

            # Contactos personales de este usuario en esta empresa
            contactos_personales = list(db["user_panic_contacts"].find({
                "usuario_id": u["_id"],
                "empresa_id": ObjectId(empresa_id)
            }).sort("nombre", 1))

            externos_grupo = []

            # Agregar contactos personales si existen
            if contactos_personales:
                externos_grupo.append({
                    "empresa_nombre": emp_nombre,
                    "tipo": "personal",
                    "contactos": serializar(contactos_personales),
                })

            resultado.append({
                "_id":                  uid,
                "nombre_completo":      nombre_completo,
                "numero_documento":     num_doc,
                "tipo_documento":       u.get("tipo_documento", "CC"),
                "label":                f"{nombre_completo} - {num_doc}",
                "externos_por_empresa": externos_grupo,
            })
        return ok(resultado)
    except Exception as e:
        return err(str(e))


# ═══════════════════════════════════════════════════════════════
# Contactos Personales del Usuario (user_panic_contacts)
# ═══════════════════════════════════════════════════════════════

@panico_bp.route("/mis-contactos", methods=["GET"])
@requiere_login
def listar_mis_contactos():
    """Obtener contactos personales del usuario en su empresa."""
    usuario_id = session.get("usuario_id")
    empresa_id = _empresa_id()
    if not usuario_id or not empresa_id:
        return err("Sin usuario o empresa", 400)
    contactos = UserPanicContactModel.listar(usuario_id, empresa_id)
    return ok(serializar(contactos))


@panico_bp.route("/mis-contactos", methods=["POST"])
@requiere_login
def crear_mi_contacto():
    """Crear contacto personal."""
    usuario_id = session.get("usuario_id")
    empresa_id = _empresa_id()
    if not usuario_id or not empresa_id:
        return err("Sin usuario o empresa", 400)
    datos = request.get_json() or {}
    exito, resultado = UserPanicContactModel.crear(
        usuario_id, empresa_id,
        datos.get("nombre", ""),
        telefono=datos.get("telefono"),
        descripcion=datos.get("descripcion", ""),
        habilitado=datos.get("habilitado", True),
        habilitado_para_sms=datos.get("habilitado_para_sms", False),
        habilitado_para_whatsapp=datos.get("habilitado_para_whatsapp", False),
        habilitado_para_llamada=datos.get("habilitado_para_llamada", False),
        prefijo=datos.get("prefijo"),
        celular=datos.get("celular")
    )
    if not exito:
        return err(resultado)
    return ok(serializar(resultado), status=201)


@panico_bp.route("/mis-contactos/<contacto_id>", methods=["PUT"])
@requiere_login
def actualizar_mi_contacto(contacto_id):
    """Actualizar contacto personal."""
    datos = request.get_json() or {}
    exito, msg = UserPanicContactModel.actualizar(contacto_id, datos)
    if not exito:
        return err(msg)
    return ok(mensaje=msg)


@panico_bp.route("/mis-contactos/<contacto_id>", methods=["DELETE"])
@requiere_login
def eliminar_mi_contacto(contacto_id):
    """Eliminar contacto personal."""
    exito, msg = UserPanicContactModel.eliminar(contacto_id)
    if not exito:
        return err(msg)
    return ok(mensaje=msg)


@panico_bp.route("/admin/migrar-contactos", methods=["POST"])
@_requiere_sistema
def admin_migrar_contactos():
    """Migrar contactos de panic_configurations a user_panic_contacts.
    (Solo administrador del sistema)"""
    datos = request.get_json() or {}
    empresa_id = datos.get("empresa_id")
    usuario_id = datos.get("usuario_id")  # Opcional: si se especifica, asigna a este usuario
    if not empresa_id:
        return err("Falta empresa_id", 400)
    exito, count = UserPanicContactModel.migrar_desde_empresa(empresa_id, usuario_id)
    if not exito:
        return err(count)
    return ok({"migrados": count})


# ═══════════════════════════════════════════════════════════════
# Traza de Twilio - Auditoría completa de peticiones
# ═══════════════════════════════════════════════════════════════

@panico_bp.route("/traza/<evento_id>", methods=["GET"])
@requiere_login
def obtener_traza_evento(evento_id):
    """Obtiene la traza completa de peticiones a Twilio para un evento.

    Formato: /traza/<evento_id>
    Retorna: Lista de todas las peticiones SMS, WhatsApp y Llamadas para ese evento
    """
    try:
        trazas = TwilioRequestLogModel.obtener_traza(evento_id)
        return ok(serializar(trazas))
    except Exception as e:
        return err(str(e))


@panico_bp.route("/traza/imprimir/<evento_id>", methods=["GET"])
@requiere_login
def imprimir_traza_evento(evento_id):
    """Imprime la traza en formato HTML legible."""
    try:
        trazas = TwilioRequestLogModel.obtener_traza(evento_id)
        if not trazas:
            return err("No hay trazas para este evento", 404)

        html = "<html><head><meta charset='utf-8'><style>"
        html += "body { font-family: Arial; margin: 20px; } "
        html += ".traza { border: 1px solid #ddd; margin: 20px 0; padding: 15px; background: #f9f9f9; } "
        html += ".tipo { font-weight: bold; color: #2787F5; font-size: 14px; } "
        html += ".contacto { color: #666; margin: 5px 0; } "
        html += ".peticion { background: #fff; padding: 10px; margin: 10px 0; border-left: 3px solid #4CAF50; } "
        html += ".respuesta { background: #fff; padding: 10px; margin: 10px 0; border-left: 3px solid #FF9800; } "
        html += ".transicion { padding: 8px; margin: 5px 0; background: #e8f4f8; border-radius: 4px; } "
        html += ".error { color: #d32f2f; background: #ffebee; padding: 10px; margin: 10px 0; } "
        html += "</style></head><body>"
        html += f"<h1>Traza de Evento: {evento_id}</h1>"

        for i, traza in enumerate(trazas, 1):
            html += '<div class="traza">'
            html += f'<div class="tipo">#{i} {traza.get("tipo_notificacion", "").upper()}</div>'
            html += f'<div class="contacto">Contacto: {traza.get("contacto_externo", {}).get("nombre")} ({traza.get("contacto_externo", {}).get("numero")})</div>'
            html += f'<div class="contacto">Usuario: {traza.get("usuario")} | Empresa: {traza.get("empresa")}</div>'
            html += f'<div class="contacto">Activado: {traza.get("activado_en")}</div>'

            html += '<div class="peticion"><strong>Petición Twilio:</strong><br>'
            for k, v in traza.get("peticion_twilio", {}).items():
                html += f'  {k}: {v}<br>'
            html += '</div>'

            html += '<div class="respuesta"><strong>Respuesta Inicial:</strong><br>'
            for k, v in traza.get("respuesta_inicial", {}).items():
                html += f'  {k}: {v}<br>'
            html += '</div>'

            if traza.get("transiciones_estado"):
                html += '<strong>Transiciones de Estado:</strong><br>'
                for trans in traza.get("transiciones_estado", []):
                    html += f'<div class="transicion">'
                    html += f'{trans.get("orden")}. {trans.get("estado")} @ {trans.get("timestamp")}'
                    if trans.get("detalles"):
                        html += f' - {trans.get("detalles")}'
                    html += '</div>'

            if traza.get("errores"):
                html += f'<div class="error"><strong>Error:</strong> {traza.get("errores")}</div>'

            html += '</div>'

        html += "</body></html>"
        from flask import make_response
        response = make_response(html)
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response
    except Exception as e:
        return err(str(e))


# ── Webhook de Twilio (recibe cambios de estado) ───────────────
@panico_bp.route("/webhook/twilio-status", methods=["POST"])
def webhook_twilio_status():
    """Recibe webhooks de Twilio cuando cambia el estado de SMS/Llamada/WhatsApp.

    Busca el evento en panic_events por SID y actualiza el historial directamente.
    """
    try:
        data = request.form if request.form else request.get_json(silent=True) or {}

        # Identificar si es SMS/WhatsApp o Llamada
        sid = data.get("MessageSid") or data.get("CallSid") or ""
        estado_raw = data.get("MessageStatus") or data.get("CallStatus") or ""
        # AMD: si Twilio detectó buzón/contestadora lo dice en AnsweredBy
        answered_by = (data.get("AnsweredBy") or "").lower()

        if not sid or not estado_raw:
            return jsonify({"ok": True}), 200  # Ignorar silenciosamente

        # Buscar el evento en panic_events que contiene este SID
        evento = db["panic_events"].find_one({
            "$or": [
                {"resultado.externos.canales.llamada.sid": sid},
                {"resultado.externos.canales.sms.sid": sid},
                {"resultado.externos.canales.whatsapp.sid": sid},
                {"resultado.directorio.canales.llamada.sid": sid},
                {"resultado.directorio.canales.sms.sid": sid},
                {"resultado.directorio.canales.whatsapp.sid": sid},
            ]
        })

        if not evento:
            return jsonify({"ok": True}), 200

        # Encontrar cuál es el tipo de canal (llamada, sms, whatsapp)
        tipo_canal = None
        contacto_encontrado = None
        lista_contactos = evento.get("resultado", {}).get("externos", []) + evento.get("resultado", {}).get("directorio", [])

        for contacto in lista_contactos:
            canales = contacto.get("canales", {})
            for canal_tipo, info_canal in canales.items():
                if info_canal.get("sid") == sid:
                    tipo_canal = canal_tipo
                    contacto_encontrado = contacto
                    break
            if tipo_canal:
                break

        if not tipo_canal or not contacto_encontrado:
            return jsonify({"ok": True}), 200

        # Convertir estado de Twilio a español LEYENDO DE LA COLECCIÓN notification_states
        # (fuente de verdad). Una sola consulta trae el nombre y la razón.
        # MAPA_ESTADOS queda solo como red de seguridad si el estado no estuviera en la BD.
        estado_raw_lower = estado_raw.lower()
        estado_doc = NotificationStateModel.obtener_estado(tipo_canal, estado_raw_lower)
        if estado_doc:
            estado_nuevo = estado_doc.get("nombreEspanol", estado_raw_lower)
            razon = estado_doc.get("razonTerminacion", "")
        else:
            estado_nuevo = MAPA_ESTADOS.get(estado_raw_lower, estado_raw_lower)
            razon = ""

        # Obtener historial actual
        historial = contacto_encontrado.get("canales", {}).get(tipo_canal, {}).get("historial", [])
        ultimo_estado = historial[-1]["estado"] if historial else ""

        # Refinar el "completed" de una llamada. Twilio reporta "completed" tanto
        # si contestó una persona, como si colgó tras contestar, como si cayó al buzón.
        # Los separamos por DURACIÓN y por AMD (AnsweredBy), en este orden de prioridad:
        if tipo_canal == "llamada" and estado_raw_lower == "completed":
            try:
                call_duration = int(data.get("CallDuration") or 0)
            except (ValueError, TypeError):
                call_duration = 0
            contesto = any(h.get("estado") == "en_llamada" for h in historial)
            es_maquina = answered_by.startswith("machine") or answered_by == "fax"

            if contesto and 0 < call_duration < 10:
                # Persona contestó y colgó rápido (el buzón nunca dura tan poco).
                estado_nuevo = "cancelado"
                razon = "El destinatario colgó antes de escuchar el mensaje"
            elif es_maquina:
                # Contestó un buzón. Con timeout=18, los "no contestó" se cortan
                # antes del buzón; si el buzón igual contestó, la línea estaba
                # ocupada / no disponible (desvío temprano) → "Ocupado".
                estado_nuevo = "ocupado"
                razon = "La línea estaba ocupada o no disponible (cayó al buzón)"

        # Si el estado cambió, agregar a historial
        if estado_nuevo != ultimo_estado:
            historial.append({
                "estado": estado_nuevo,
                "en": datetime.utcnow().isoformat(),
            })
            if razon:
                historial[-1]["detalle"] = razon

            # Actualizar en panic_events usando update_one con la ruta exacta
            update_path = None
            es_externo = False

            # Encontrar el índice del contacto en externos o directorio
            for i, c in enumerate(evento.get("resultado", {}).get("externos", [])):
                if c.get("numero") == contacto_encontrado.get("numero"):
                    update_path = f"resultado.externos.{i}.canales.{tipo_canal}"
                    es_externo = True
                    break

            if not update_path:
                for i, c in enumerate(evento.get("resultado", {}).get("directorio", [])):
                    if c.get("numero") == contacto_encontrado.get("numero"):
                        update_path = f"resultado.directorio.{i}.canales.{tipo_canal}"
                        break

            if update_path:
                db["panic_events"].update_one(
                    {"_id": evento["_id"]},
                    {
                        "$set": {
                            f"{update_path}.historial": historial,
                            f"{update_path}.estado": estado_nuevo,
                            "estados_actualizados_en": datetime.now(timezone.utc)
                        }
                    }
                )
                log.info("Twilio %s %s → %s", tipo_canal,
                         contacto_encontrado.get("numero", ""), estado_nuevo)

        return jsonify({"ok": True}), 200

    except Exception as e:
        log.error("Error en webhook Twilio: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# DEBUG: Ver contenido de user_panic_contacts
# ═══════════════════════════════════════════════════════════════

