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
from app.servicios.boton_panico.model import PanicConfigModel, PanicEventModel, UserPanicContactModel

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


_ESTADOS_PENDIENTES = {"enviado", "sent", "initiated", "iniciado", "queued",
                       "ringing", "sending", "in-progress"}
_ESTADOS_FINALES    = {"delivered", "read", "completed", "failed", "undelivered",
                       "no-answer", "busy", "canceled", "mock", "error"}

# Jerarquía ordenada por canal (para el frontend)
JERARQUIA_ESTADOS = {
    "sms":      ["queued", "sending", "sent", "delivered", "undelivered", "failed"],
    "whatsapp": ["queued", "sending", "sent", "delivered", "read", "failed", "undelivered"],
    "llamada":  ["queued", "initiated", "ringing", "in-progress", "completed",
                 "no-answer", "busy", "canceled", "failed"],
}


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
    """Refresca estados desde Twilio para una lista de evento_ids."""
    datos      = request.get_json(silent=True) or {}
    evento_ids = datos.get("evento_ids", [])
    solo_pendientes = datos.get("solo_pendientes", True)

    if not evento_ids:
        return err("evento_ids requerido", 400)

    try:
        from app.servicios.boton_panico.controller import _twilio_client
        cliente = _twilio_client()
        if not cliente:
            return err("Sin credenciales Twilio", 400)

        actualizados = 0
        for eid_str in evento_ids[:30]:  # máx 30 por lote
            try:
                ev = db["panic_events"].find_one({"_id": ObjectId(eid_str)})
                if not ev:
                    continue
                resultado  = ev.get("resultado", {})
                cambio     = False
                for grupo in ("externos", "directorio"):
                    for contacto in resultado.get(grupo, []):
                        for tipo, info in list((contacto.get("canales") or {}).items()):
                            sid = info.get("sid", "")
                            estado_actual = (info.get("estado") or "").lower()
                            if not sid:
                                continue
                            if solo_pendientes and estado_actual not in _ESTADOS_PENDIENTES:
                                continue
                            try:
                                if tipo in ("sms", "whatsapp"):
                                    nuevo = cliente.messages(sid).fetch().status
                                else:
                                    nuevo = cliente.calls(sid).fetch().status
                                if nuevo and nuevo != info.get("estado"):
                                    # Acumular historial en vez de sobreescribir
                                    historial = info.get("historial") or [
                                        {"estado": info.get("estado",""), "en": "—"}
                                    ]
                                    # Solo agregar si el estado no está ya en historial
                                    estados_vistos = {h["estado"] for h in historial}
                                    if nuevo not in estados_vistos:
                                        historial.append({
                                            "estado": nuevo,
                                            "en": datetime.utcnow().isoformat(),
                                        })
                                    info["estado"]    = nuevo
                                    info["historial"] = historial
                                    cambio = True
                            except Exception:
                                pass
                if cambio:
                    db["panic_events"].update_one(
                        {"_id": ev["_id"]},
                        {"$set": {"resultado": resultado,
                                  "estados_actualizados_en": datetime.utcnow()}},
                    )
                    actualizados += 1
            except Exception:
                pass

        from flask import jsonify as _j
        return _j({"ok": True, "actualizados": actualizados})
    except Exception as e:
        return err(str(e))


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
                        # Verificar estado
                        if estado_fil and not _estado_coincide(info_canal.get("estado", ""), estado_fil):
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
        from flask import jsonify
        return jsonify({
            "ok": True,
            "data": serializar(pagina_data),
            "total": total,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "total_paginas": max(1, -(-total // por_pagina)),
        })
    except Exception as e:
        return err(str(e))


def _normalizar_estado(estado: str) -> str:
    """Normaliza estados de Twilio a categorías simples."""
    e = (estado or "").lower()
    if e in ("enviado", "sent", "delivered", "read", "initiated", "iniciado",
             "completed", "in-progress", "ringing", "queued"):
        return "ok"
    if e in ("mock",):
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


@panico_bp.route("/admin/refresh-estados", methods=["POST"])
@requiere_login
@_requiere_permiso("log")
def admin_refresh_estados():
    """Consulta Twilio por el SID de cada canal y actualiza el estado en panic_events."""
    datos       = request.get_json(silent=True) or {}
    evento_id   = datos.get("evento_id", "").strip()
    if not evento_id:
        return err("evento_id requerido", 400)
    try:
        from bson import ObjectId as OID
        ev = db["panic_events"].find_one({"_id": OID(evento_id)})
        if not ev:
            return err("Evento no encontrado", 404)

        # Obtener cliente Twilio
        from app.servicios.boton_panico.controller import _twilio_client
        cliente = _twilio_client()
        if not cliente:
            return err("Sin credenciales Twilio — no se puede consultar estado", 400)

        resultado = ev.get("resultado", {})
        actualizado = False

        for grupo in ("externos", "directorio"):
            for contacto in resultado.get(grupo, []):
                canales = contacto.get("canales", {})
                for tipo, info in list(canales.items()):
                    sid = info.get("sid", "")
                    if not sid or info.get("estado") in ("mock", "error"):
                        continue
                    nuevo_estado = None
                    try:
                        if tipo in ("sms", "whatsapp"):
                            msg = cliente.messages(sid).fetch()
                            nuevo_estado = msg.status   # queued/sent/delivered/read/failed/undelivered
                        elif tipo == "llamada":
                            call = cliente.calls(sid).fetch()
                            nuevo_estado = call.status  # queued/ringing/in-progress/completed/busy/failed/no-answer/canceled
                    except Exception as e:
                        nuevo_estado = f"error_twilio: {e}"

                    if nuevo_estado and nuevo_estado != info.get("estado"):
                        historial = info.get("historial") or [
                            {"estado": info.get("estado",""), "en": "—"}
                        ]
                        estados_vistos = {h["estado"] for h in historial}
                        if nuevo_estado not in estados_vistos:
                            historial.append({
                                "estado": nuevo_estado,
                                "en": datetime.utcnow().isoformat(),
                            })
                        info["estado"]    = nuevo_estado
                        info["historial"] = historial
                        actualizado = True

        if actualizado:
            db["panic_events"].update_one(
                {"_id": OID(evento_id)},
                {"$set": {"resultado": resultado, "estados_actualizados_en": datetime.utcnow()}},
            )

        from flask import jsonify as _jsonify
        return _jsonify({"ok": True, "data": serializar(resultado), "actualizado": actualizado})
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

        # Config de pánico de esta empresa (única)
        cfg_emp = db["panic_configurations"].find_one({"empresa_id": ObjectId(empresa_id)}) or {}
        externos_empresa = cfg_emp.get("contactos_externos", [])
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

            # Agregar contactos de empresa si existen
            if externos_empresa:
                externos_grupo.append({
                    "empresa_nombre": emp_nombre,
                    "tipo": "empresa",
                    "contactos": externos_empresa,
                })

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
        datos.get("telefono", ""),
        datos.get("descripcion", ""),
        datos.get("habilitado", True)
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
# DEBUG: Ver contenido de user_panic_contacts
# ═══════════════════════════════════════════════════════════════

@panico_bp.route("/debug/contactos-bd", methods=["GET"])
@requiere_login
def debug_contactos_bd():
    """[DEBUG] Ver qué hay en user_panic_contacts"""
    try:
        from bson import ObjectId
        usuario_id = session.get("usuario_id")
        empresa_id = session.get("empresa_id")

        resultado = {
            "usuario_id": usuario_id,
            "empresa_id": empresa_id,
            "mis_contactos": [],
            "total_en_bd": 0,
        }

        # Mis contactos
        if usuario_id and empresa_id:
            mis = list(db["user_panic_contacts"].find({
                "usuario_id": ObjectId(usuario_id),
                "empresa_id": ObjectId(empresa_id)
            }))
            resultado["mis_contactos"] = serializar(mis)

        # Total en toda la colección
        total = db["user_panic_contacts"].count_documents({})
        resultado["total_en_bd"] = total

        # Mostrar todos (para debug)
        todos = list(db["user_panic_contacts"].find({}))
        resultado["todos_los_contactos"] = serializar(todos)

        return ok(resultado)
    except Exception as e:
        return err(str(e))


@panico_bp.route("/debug/evento-raw", methods=["GET"])
@requiere_login
def debug_evento_raw():
    """[DEBUG] Mostrar un evento RAW tal como está en la BD"""
    try:
        if not session.get("es_sistema"):
            return err("Solo superadmin", 400)

        empresa_id = request.args.get("empresa_id")
        if not empresa_id:
            # Mostrar empresas disponibles
            empresas = list(db["panic_events"].distinct("empresa_id"))
            return ok({
                "mensaje": "Pasa ?empresa_id=xxx",
                "empresas_disponibles": [str(e) for e in empresas]
            })

        # Obtener el último evento
        ev = db["panic_events"].find_one(
            {"empresa_id": ObjectId(empresa_id)},
            sort=[("activado_en", -1)]
        )

        if not ev:
            return ok({"mensaje": "No hay eventos en esta empresa"})

        # Convertir ObjectId a string para poder serializarlo
        ev["_id"] = str(ev["_id"])
        ev["empresa_id"] = str(ev["empresa_id"])
        if ev.get("activado_en"):
            ev["activado_en"] = ev["activado_en"].isoformat()

        return ok({"evento": ev})
    except Exception as e:
        return err(f"Error: {str(e)}")


@panico_bp.route("/debug/validar-log", methods=["GET"])
@requiere_login
def debug_validar_log():
    """[DEBUG] Validar que los eventos se almacenan correctamente y probar filtros"""
    try:
        # Verificar que sea del sistema
        if not session.get("es_sistema"):
            return err("Solo superadmin", 400)

        empresa_id = request.args.get("empresa_id")
        if not empresa_id:
            return err("Necesita ?empresa_id=xxx", 400)

        # Obtener últimos 5 eventos
        eventos = list(db["panic_events"].find(
            {"empresa_id": ObjectId(empresa_id)}
        ).sort("activado_en", -1).limit(5))

        if not eventos:
            return ok({"mensaje": "No hay eventos", "empresa_id": empresa_id})

        resultado = {
            "total_eventos": db["panic_events"].count_documents({"empresa_id": ObjectId(empresa_id)}),
            "últimos_eventos": []
        }

        for ev in eventos:
            res = ev.get("resultado", {})
            externos = res.get("externos", [])
            directorio = res.get("directorio", [])

            evento_info = {
                "evento_id": str(ev.get("_id")),
                "fecha": ev.get("activado_en"),
                "nombre_residente": ev.get("nombre_residente"),
                "bloqueado": res.get("bloqueado", False),
                "contactos_externos": [],
                "contactos_directorio": [],
                "canales_encontrados": set()
            }

            # Analizar externos
            for c in externos:
                canales = c.get("canales", {})
                contacto_info = {
                    "nombre": c.get("nombre"),
                    "numero": c.get("numero"),
                    "canales": {}
                }
                for tipo, data in canales.items():
                    contacto_info["canales"][tipo] = {
                        "estado": data.get("estado"),
                        "sid": data.get("sid", "—")
                    }
                    evento_info["canales_encontrados"].add(tipo)
                evento_info["contactos_externos"].append(contacto_info)

            # Analizar directorio
            for c in directorio:
                canales = c.get("canales", {})
                contacto_info = {
                    "nombre": c.get("nombre"),
                    "numero": c.get("numero"),
                    "canales": {}
                }
                for tipo, data in canales.items():
                    contacto_info["canales"][tipo] = {
                        "estado": data.get("estado"),
                        "sid": data.get("sid", "—")
                    }
                    evento_info["canales_encontrados"].add(tipo)
                evento_info["contactos_directorio"].append(contacto_info)

            evento_info["canales_encontrados"] = list(evento_info["canales_encontrados"])
            resultado["últimos_eventos"].append(evento_info)

        return ok(resultado)
    except Exception as e:
        return err(str(e))


@panico_bp.route("/debug/probar-filtros", methods=["GET"])
@requiere_login
def debug_probar_filtros():
    """[DEBUG] Probar filtros manualmente"""
    try:
        if not session.get("es_sistema"):
            return err("Solo superadmin", 400)

        empresa_id = request.args.get("empresa_id")
        canal_fil = request.args.get("canal", "").strip().lower()

        if not empresa_id:
            return err("Necesita ?empresa_id=xxx", 400)

        # Obtener TODOS los eventos
        todos = list(db["panic_events"].find(
            {"empresa_id": ObjectId(empresa_id)}
        ).sort("activado_en", -1))

        resultado = {
            "total_sin_filtro": len(todos),
            "filtro_aplicado": f"canal={canal_fil}" if canal_fil else "sin filtro",
            "eventos_sin_filtro": [],
            "eventos_con_filtro": [],
            "detalles_filtrado": []
        }

        # Mostrar estructura de primeros 2 eventos sin filtro
        for ev in todos[:2]:
            res = ev.get("resultado", {})
            resultado["eventos_sin_filtro"].append({
                "evento_id": str(ev.get("_id")),
                "nombre_residente": ev.get("nombre_residente"),
                "canales": []
            })

            externos = res.get("externos", [])
            directorio = res.get("directorio", [])
            for c in externos + directorio:
                for tipo in (c.get("canales") or {}).keys():
                    resultado["eventos_sin_filtro"][-1]["canales"].append(tipo)

        # Aplicar filtro si existe
        if canal_fil:
            filtrados = []
            for ev in todos:
                res = ev.get("resultado", {})
                externos = res.get("externos", [])
                directorio = res.get("directorio", [])

                evento_coincide = False
                detalles = {
                    "evento_id": str(ev.get("_id")),
                    "contactos_revisados": []
                }

                for c in externos + directorio:
                    canales = c.get("canales", {})
                    for tipo, data in canales.items():
                        detalle = {
                            "nombre": c.get("nombre"),
                            "canal": tipo,
                            "canal.lower()": tipo.lower(),
                            "canal_fil": canal_fil,
                            "coincide": tipo.lower() == canal_fil,
                            "estado": data.get("estado")
                        }
                        detalles["contactos_revisados"].append(detalle)

                        if tipo.lower() == canal_fil:
                            evento_coincide = True

                if evento_coincide:
                    filtrados.append(ev)
                    resultado["detalles_filtrado"].append(detalles)

            resultado["eventos_con_filtro"] = [
                {
                    "evento_id": str(ev.get("_id")),
                    "nombre_residente": ev.get("nombre_residente")
                }
                for ev in filtrados
            ]
            resultado["total_con_filtro"] = len(filtrados)

        return ok(resultado)
    except Exception as e:
        return err(str(e))


@panico_bp.route("/debug/estructura-evento", methods=["GET"])
@requiere_login
def debug_estructura_evento():
    """[DEBUG] Ver estructura de un evento de pánico"""
    try:
        # Permitir superadmin pasar empresa_id por param
        eid = request.args.get("empresa_id") or _empresa_admin()
        if not eid:
            return err("Necesitas ser admin o pasar ?empresa_id=xxx", 400)

        # Verificar que el usuario sea del sistema
        if not session.get("es_sistema"):
            return err("Solo superadmin", 400)

        # Obtener el primer evento
        ev = db["panic_events"].find_one({"empresa_id": ObjectId(eid)})
        if not ev:
            return ok({"mensaje": "No hay eventos en esta empresa"})

        # Si no hay eventos, mostrar las empresas disponibles
        if not ev:
            empresas = list(db["panic_events"].find(
                {}, {"empresa_id": 1}
            ).distinct("empresa_id"))
            return ok({
                "mensaje": "No hay eventos en esta empresa",
                "empresas_disponibles": [str(e) for e in empresas],
                "instruccion": "Pasa ?empresa_id=xxx con una de las empresas"
            })

        resultado = {
            "evento_id": str(ev.get("_id")),
            "empresa_id": str(ev.get("empresa_id")),
            "nombre_residente": ev.get("nombre_residente"),
            "activado_en": ev.get("activado_en"),
            "resultado_keys": list((ev.get("resultado") or {}).keys()),
            "resultado_completo": serializar(ev.get("resultado", {})),
            "estructura_externos": None,
            "estructura_directorio": None,
        }

        # Ver estructura de externos
        externos = ev.get("resultado", {}).get("externos", [])
        if externos:
            resultado["estructura_externos"] = serializar(externos[0])

        # Ver estructura de directorio
        directorio = ev.get("resultado", {}).get("directorio", [])
        if directorio:
            resultado["estructura_directorio"] = serializar(directorio[0])

        return ok(resultado)
    except Exception as e:
        return err(str(e))
