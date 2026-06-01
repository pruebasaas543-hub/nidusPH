"""
app/auth/routes.py
──────────────────
Rutas de autenticación: login, logout, selección de empresa y dashboard.

Flujo post-login:
  SuperAdmin / ImplementadorNidus → /config/
  Usuario con 1 empresa            → /dashboard/  (auto-selección)
  Usuario con N empresas           → /seleccionar-empresa  (pantalla de elección)
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, session
from app.auth.controller import AuthController

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/")

# ── Helpers ────────────────────────────────────────────────────────────────

def _tipos_documento() -> list:
    """Carga tipos de documento desde tipo_identificador_fiscal con fallback en memoria."""
    from app import db
    tipos = list(db["tipo_identificador_fiscal"].find(
        {}, {"_id": 0, "id_sigla": 1, "nombre": 1, "tipo_persona": 1}
    ).sort("codigo_dian", 1))
    if not tipos:
        from app.auth.model import TIPOS_DOCUMENTO
        tipos = [
            {"id_sigla": k, "nombre": v["nombre"], "tipo_persona": v.get("tipo_persona", "Natural")}
            for k, v in TIPOS_DOCUMENTO.items()
        ]
    return tipos


def _modulos_visibles() -> list:
    """Devuelve servicios accesibles = intersección(rol.modulos, plan.modulos_incluidos)."""
    from app import db
    from bson import ObjectId

    empresa_id = session.get("empresa_id")
    rol_nombre = session.get("rol")
    if not empresa_id or not rol_nombre:
        return []

    rol_doc = db["roles"].find_one({"nombre": rol_nombre}, {"modulos": 1})
    if not rol_doc:
        return []
    ids_rol = {str(m) for m in rol_doc.get("modulos", [])}
    if not ids_rol:
        return []

    empresa = db["empresas"].find_one({"_id": ObjectId(empresa_id)}, {"plan": 1})
    if not empresa or not empresa.get("plan"):
        return []

    from app.configuracion.planes.model import PlanModel
    plan = PlanModel.buscar_por_id(str(empresa["plan"]))
    if not plan:
        return []
    ids_plan = {str(m) for m in plan.get("modulos_incluidos", [])}

    ids_comunes = ids_rol & ids_plan
    if not ids_comunes:
        return []

    servicios = list(db["servicios"].find(
        {"_id": {"$in": [ObjectId(i) for i in ids_comunes]}, "activo": True},
        {"nombre": 1, "icono": 1, "descripcion": 1, "codigo": 1, "orden": 1}
    ).sort("orden", 1))
    return servicios


def _redirigir_segun_rol(rol: str):
    logger.debug("Redirigiendo rol='%s' a su panel", rol)
    from app.configuracion.roles.model import RolModel
    if rol in RolModel.nombres_sistema():
        return redirect(url_for("config_panel.panel"))
    return redirect(url_for("auth.dashboard"))


def _redirigir_con_primer_login(num_doc: str, destino_rol: str):
    """Si es primer login emite token de cambio de clave; si no, redirige normal."""
    if session.get("primer_login"):
        from app.recuperacion.model import RecuperacionModel
        import secrets
        token = secrets.token_urlsafe(32)
        RecuperacionModel.guardar_token(num_doc, token)
        return redirect(url_for("recuperacion.nueva_password_get", token=token))
    return _redirigir_segun_rol(destino_rol)


# ── Rutas ──────────────────────────────────────────────────────────────────

@auth_bp.route("/", methods=["GET"])
@auth_bp.route("/login", methods=["GET"])
def login_get():
    if "usuario_id" in session:
        # Si hay selección pendiente, retomar el flujo
        if session.get("pendiente_seleccion"):
            return redirect(url_for("auth.seleccionar_empresa"))
        return _redirigir_segun_rol(session.get("rol", ""))
    return render_template("auth/login.html", tipos_doc=_tipos_documento())


@auth_bp.route("/login", methods=["POST"])
def login_post():
    tipo_doc   = request.form.get("tipoDoc",    "").strip()
    num_doc    = request.form.get("numDoc",     "").strip()
    password   = request.form.get("password",   "")
    empresa_id = request.form.get("empresa_id", "").strip() or None

    logger.info("Intento de login: tipo=%s num=%s empresa_id=%s", tipo_doc, num_doc, empresa_id)

    exito, resultado = AuthController.login(tipo_doc, num_doc, password, empresa_id=empresa_id)

    if not exito:
        logger.warning("Login fallido: %s", resultado)
        branding = None
        if empresa_id:
            from app.slug.controller import SlugController
            from app import db
            from bson import ObjectId
            try:
                emp = db["empresas"].find_one({"_id": ObjectId(empresa_id)}, {"slug": 1})
                if emp and emp.get("slug"):
                    branding = SlugController.contexto_branding(emp["slug"])
            except Exception:
                pass
        return render_template("auth/login.html",
                               error=resultado,
                               branding=branding,
                               tipos_doc=_tipos_documento(),
                               form_data={"tipoDoc": tipo_doc, "numDoc": num_doc})

    logger.info("Login exitoso: num=%s resultado=%s", num_doc, resultado)

    if resultado == "__SELECCIONAR_EMPRESA__":
        return redirect(url_for("auth.seleccionar_empresa"))

    return _redirigir_con_primer_login(num_doc, resultado)


# ── Selección de empresa ───────────────────────────────────────────────────

@auth_bp.route("/seleccionar-empresa", methods=["GET"])
def seleccionar_empresa():
    """Pantalla intermedia: el usuario elige en cuál empresa quiere trabajar."""
    if "usuario_id" not in session:
        return redirect(url_for("auth.login_get"))
    opciones = session.get("pendiente_seleccion", [])
    if not opciones:
        return redirect(url_for("auth.dashboard"))
    return render_template(
        "auth/seleccionar_empresa.html",
        opciones=opciones,
        nombres=session.get("nombres", ""),
    )


@auth_bp.route("/seleccionar-empresa", methods=["POST"])
def confirmar_empresa():
    """Procesa la empresa elegida y establece la sesión completa."""
    if "usuario_id" not in session:
        return redirect(url_for("auth.login_get"))

    empresa_id_sel = request.form.get("empresa_id", "").strip()
    opciones       = session.get("pendiente_seleccion", [])
    seleccionada   = next((o for o in opciones if o["empresa_id"] == empresa_id_sel), None)

    if not seleccionada:
        return redirect(url_for("auth.seleccionar_empresa"))

    session["rol"]            = seleccionada["rol_asignado"]
    session["empresa_id"]     = seleccionada["empresa_id"]
    session["empresa_nombre"] = seleccionada["empresa_nombre"]
    session["empresa_slug"]   = seleccionada.get("empresa_slug", "")
    session.pop("pendiente_seleccion", None)

    return _redirigir_con_primer_login(session["num_doc"], seleccionada["rol_asignado"])


@auth_bp.route("/cambiar-empresa")
def cambiar_empresa():
    """Permite al usuario multi-empresa cambiar de contexto sin cerrar sesión."""
    if "usuario_id" not in session:
        return redirect(url_for("auth.login_get"))

    from app import db
    from bson import ObjectId

    try:
        uid = ObjectId(session["usuario_id"])
    except Exception:
        return redirect(url_for("auth.login_get"))

    asociaciones = list(db["asociaciones"].aggregate([
        {"$match": {"user_id": uid, "activo": True}},
        {"$lookup": {"from": "empresas", "localField": "empresa_id",
                     "foreignField": "_id", "as": "empresa"}},
        {"$unwind": {"path": "$empresa", "preserveNullAndEmptyArrays": True}},
        {"$project": {
            "empresa_id":     1,
            "rol_asignado":   1,
            "empresa_nombre": "$empresa.razon_social",
            "empresa_slug":   "$empresa.slug",
        }},
    ]))

    session["pendiente_seleccion"] = [
        {
            "empresa_id":     str(a["empresa_id"]),
            "empresa_nombre": a.get("empresa_nombre", ""),
            "empresa_slug":   a.get("empresa_slug", ""),
            "rol_asignado":   a["rol_asignado"],
        }
        for a in asociaciones
    ]
    return redirect(url_for("auth.seleccionar_empresa"))


# ── Dashboard ──────────────────────────────────────────────────────────────

# Variables CSS por tema — para inyectar en el servidor sin depender de JS
_VARS_CSS = {
    "default":     ":root{--bg:#EEF2FF;--bg2:#FFFFFF;--bg3:#D8E4F5;--bg4:#C0D2EE;--accent:#2787F5;--accent2:#1a6de0;--text:#1E2756;--muted:rgba(30,39,86,.45);--border:rgba(39,135,245,.18);--red:#DC2626;--green:#16A34A;}",
    "oscuro-cyan": ":root{--bg:#0B0F17;--bg2:#111827;--bg3:#1F2937;--bg4:#273449;--accent:#06B6D4;--accent2:#0284C7;--text:#F8FAFC;--muted:rgba(248,250,252,.42);--border:rgba(6,182,212,.18);}",
    "galaxia":     ":root{--bg:#090D16;--bg2:#151D30;--bg3:#0F1524;--bg4:#1A2540;--accent:#FB7185;--accent2:#E11D48;--text:#F5EFE9;--muted:rgba(245,239,233,.42);--border:rgba(251,113,133,.18);}",
    "bosque":      ":root{--bg:#F3F4F6;--bg2:#FFFFFF;--bg3:#E5E7EB;--bg4:#D1D5DB;--accent:#606C5D;--accent2:#4A5548;--text:#111827;--muted:rgba(17,24,39,.5);--border:rgba(96,108,93,.2);--red:#DC2626;--green:#16A34A;}",
    "grafito":     ":root{--bg:#F1F3F5;--bg2:#FFFFFF;--bg3:#E5E8ED;--bg4:#D1D5DA;--accent:#606C5D;--accent2:#4A5548;--text:#2B303A;--muted:rgba(43,48,58,.5);--border:rgba(96,108,93,.2);--red:#DC2626;--green:#16A34A;}",
    "calido":      ":root{--bg:#FAF9F6;--bg2:#FFFFFF;--bg3:#F2F2F7;--bg4:#E5E5EA;--accent:#1C1C1E;--accent2:#2C2C2E;--text:#1C1C1E;--muted:rgba(28,28,30,.5);--border:rgba(28,28,30,.12);--red:#DC2626;--green:#16A34A;}",
    "polar":       ":root{--bg:#F4F6F8;--bg2:#FFFFFF;--bg3:#EAF0F5;--bg4:#D6E4EE;--accent:#4A7B9D;--accent2:#3D6682;--text:#1E252B;--muted:rgba(30,37,43,.5);--border:rgba(74,123,157,.2);--red:#DC2626;--green:#16A34A;}",
}


def _tema_efectivo(empresa_id: str) -> tuple:
    """Devuelve el tema considerando primero la preferencia del usuario en sesión."""
    prefs = session.get("tema_prefs", {})
    pref_clave = prefs.get(empresa_id, "") if empresa_id else ""
    if pref_clave:
        try:
            from app import db
            tema = db["apariencias"].find_one({"clave": pref_clave, "activo": True})
            if tema:
                return pref_clave, tema.get("css", ""), _VARS_CSS.get(pref_clave, "")
        except Exception:
            pass
    return _tema_empresa(empresa_id)


def _tema_empresa(empresa_id: str) -> tuple:
    """Devuelve (clave, css) del tema activo de la empresa.

    Si hay varios asociados, prefiere el más reciente que NO sea 'default'.
    Si todos son 'default', devuelve el más reciente.
    """
    if not empresa_id:
        return "default", "", _VARS_CSS.get("default", "")
    try:
        from app import db
        from bson import ObjectId
        oid = ObjectId(empresa_id)

        # 1) Buscar el tema no-default más reciente
        asoc = db["apariencia_empresa"].find_one(
            {"empresa_id": oid},
            sort=[("creado_en", -1)],
        )
        if not asoc:
            logger.info("_tema_empresa: empresa_id=%s sin apariencia configurada", empresa_id)
            return "default", "", _VARS_CSS.get("default", "")

        # Si el más reciente es default, intentar obtener uno no-default
        tema = db["apariencias"].find_one({"_id": asoc["apariencia_id"]})
        if tema and tema.get("clave", "default") == "default":
            # Hay un default como más reciente; buscar uno no-default
            no_defaults = list(db["apariencia_empresa"].find(
                {"empresa_id": oid},
                sort=[("creado_en", -1)],
            ))
            for nd in no_defaults:
                t = db["apariencias"].find_one({"_id": nd["apariencia_id"]})
                if t and t.get("clave", "default") != "default":
                    tema = t
                    break

        if not tema:
            logger.warning("_tema_empresa: apariencia_id=%s no existe en apariencias", asoc.get("apariencia_id"))
            return "default", "", _VARS_CSS.get("default", "")

        clave = tema.get("clave", "default")
        logger.info("_tema_empresa: empresa_id=%s → tema='%s'", empresa_id, clave)
        return clave, tema.get("css", ""), _VARS_CSS.get(clave, "")
    except Exception as exc:
        logger.exception("_tema_empresa: error para empresa_id=%s: %s", empresa_id, exc)
    return "default", "", ""


@auth_bp.route("/dashboard")
def dashboard():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login_get"))
    from app.configuracion.roles.model import RolModel
    if session.get("rol") in RolModel.nombres_sistema():
        return redirect(url_for("config_panel.panel"))
    if session.get("pendiente_seleccion"):
        return redirect(url_for("auth.seleccionar_empresa"))
    empresa_id = session.get("empresa_id", "")
    tema_clave, tema_css, tema_vars = _tema_efectivo(empresa_id)
    return render_template("auth/dashboard.html",
                           nombres=session.get("nombres", ""),
                           rol=session.get("rol", ""),
                           empresa_nombre=session.get("empresa_nombre", ""),
                           empresa_id=empresa_id,
                           num_empresas=session.get("num_empresas", 0),
                           modulos=_modulos_visibles(),
                           tema_clave=tema_clave,
                           tema_css=tema_css,
                           tema_vars=tema_vars)


@auth_bp.route("/mi-apariencia")
def mi_apariencia():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login_get"))
    from app.configuracion.roles.model import RolModel
    if session.get("rol") in RolModel.nombres_sistema():
        return redirect(url_for("config_panel.panel"))
    if session.get("pendiente_seleccion"):
        return redirect(url_for("auth.seleccionar_empresa"))

    empresa_id = session.get("empresa_id", "")
    tema_clave, tema_css, tema_vars = _tema_efectivo(empresa_id)

    temas = []
    if empresa_id:
        try:
            from app import db
            from bson import ObjectId
            asocs = list(db["apariencia_empresa"].find({"empresa_id": ObjectId(empresa_id)}))
            ids = [a["apariencia_id"] for a in asocs]
            temas = list(db["apariencias"].find(
                {"_id": {"$in": ids}, "activo": True},
            ).sort("orden", 1))
        except Exception:
            pass

    return render_template("auth/mi_apariencia.html",
                           nombres=session.get("nombres", ""),
                           rol=session.get("rol", ""),
                           empresa_nombre=session.get("empresa_nombre", ""),
                           empresa_id=empresa_id,
                           num_empresas=session.get("num_empresas", 0),
                           tema_clave=tema_clave,
                           tema_css=tema_css,
                           tema_vars=tema_vars,
                           temas=temas)


@auth_bp.route("/mis-modulos/<codigo>")
def modulo_usuario(codigo):
    if "usuario_id" not in session:
        return redirect(url_for("auth.login_get"))
    from app.configuracion.roles.model import RolModel
    if session.get("rol") in RolModel.nombres_sistema():
        return redirect(url_for("config_panel.panel"))
    if session.get("pendiente_seleccion"):
        return redirect(url_for("auth.seleccionar_empresa"))

    empresa_id = session.get("empresa_id", "")
    tema_clave, tema_css, tema_vars = _tema_efectivo(empresa_id)
    modulos = _modulos_visibles()

    modulo_actual = next((m for m in modulos if m.get("codigo") == codigo), None)
    if not modulo_actual:
        return redirect(url_for("auth.dashboard"))

    return render_template("auth/usuario_modulo.html",
                           nombres=session.get("nombres", ""),
                           rol=session.get("rol", ""),
                           empresa_nombre=session.get("empresa_nombre", ""),
                           empresa_id=empresa_id,
                           num_empresas=session.get("num_empresas", 0),
                           modulos=modulos,
                           modulo_actual=modulo_actual,
                           codigo=codigo,
                           tema_clave=tema_clave,
                           tema_css=tema_css,
                           tema_vars=tema_vars)


@auth_bp.route("/mi-apariencia/aplicar", methods=["POST"])
def mi_apariencia_aplicar():
    if "usuario_id" not in session:
        from flask import jsonify
        return jsonify({"ok": False, "error": "sin sesión"}), 401
    from flask import jsonify, request as req
    data = req.get_json(silent=True) or {}
    clave = str(data.get("clave", "")).strip()
    empresa_id = session.get("empresa_id", "")
    if not clave or not empresa_id:
        return jsonify({"ok": False, "error": "datos incompletos"}), 400
    prefs = dict(session.get("tema_prefs", {}))
    prefs[empresa_id] = clave
    session["tema_prefs"] = prefs
    session.modified = True
    logger.info("tema_prefs: empresa=%s → clave='%s'", empresa_id, clave)
    return jsonify({"ok": True, "clave": clave})


@auth_bp.route("/logout")
def logout():
    logger.info("Logout: num=%s", session.get("num_doc", "desconocido"))
    slug = session.get("empresa_slug", "")
    AuthController.logout()
    if slug:
        return redirect(url_for("slug.portal_empresa", slug=slug))
    return redirect(url_for("auth.login_get"))