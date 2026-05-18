"""
app/slug/routes.py
──────────────────
Rutas públicas del portal por empresa:
  GET /portal/<slug>/                 → página de acceso personalizada
  GET /portal/<slug>/imagen/<campo>   → sirve logo o imágenes del carrusel

Nota: Se usa prefijo /portal/ para no chocar con las rutas existentes
      (/login, /config, /recuperar-contrasena, /dashboard).
"""

import base64
import logging
from flask import Blueprint, render_template, send_file, abort, redirect, url_for, request as _request
from io import BytesIO
from app.slug.controller import SlugController

logger = logging.getLogger(__name__)

slug_bp = Blueprint("slug", __name__, url_prefix="/portal")


@slug_bp.route("/<slug>/", methods=["GET", "POST"])
def portal_empresa(slug):
    """GET: muestra login con branding. POST: procesa credenciales manteniendo la URL del slug."""
    exito, empresa = SlugController.resolver(slug)
    if not exito:
        logger.warning("Slug no resuelto: '%s' — %s", slug, empresa)
        return redirect(url_for("auth.login_get"))

    branding = SlugController.contexto_branding(slug)

    if _request.method == "GET":
        return render_template("auth/login.html", branding=branding)

    # ── POST: delegar al controlador de auth ───────────────────────────────
    from flask import session
    from app.auth.controller import AuthController

    tipo_doc   = _request.form.get("tipoDoc",    "").strip()
    num_doc    = _request.form.get("numDoc",     "").strip()
    password   = _request.form.get("password",   "")
    empresa_id = branding.get("empresa_id")   # siempre el de este slug

    logger.info("Login via slug=%s tipo=%s num=%s", slug, tipo_doc, num_doc)

    exito_login, resultado = AuthController.login(
        tipo_doc, num_doc, password, empresa_id=empresa_id
    )

    if not exito_login:
        logger.warning("Login fallido slug=%s: %s", slug, resultado)
        return render_template("auth/login.html",
                               branding=branding,
                               error=resultado,
                               form_data={"tipoDoc": tipo_doc, "numDoc": num_doc})

    logger.info("Login exitoso slug=%s num=%s rol=%s", slug, num_doc, resultado)

    if resultado == "__SELECCIONAR_EMPRESA__":
        return redirect(url_for("auth.seleccionar_empresa"))

    # primer_login → forzar cambio de contraseña
    if session.get("primer_login"):
        import secrets
        from app.recuperacion.model import RecuperacionModel
        token = secrets.token_urlsafe(32)
        RecuperacionModel.guardar_token(num_doc, token)
        return redirect(url_for("recuperacion.nueva_password_get", token=token))

    from app.configuracion.roles.model import RolModel
    if resultado in RolModel.nombres_sistema():
        return redirect(url_for("config_panel.panel"))
    return redirect(url_for("auth.dashboard"))


@slug_bp.route("/<slug>/imagen/<campo>", methods=["GET"])
def imagen_empresa(slug, campo):
    """Sirve una imagen del branding (logo, carousel_1, etc.)"""
    exito, resultado = SlugController.obtener_imagen(slug, campo)
    if not exito:
        abort(404)

    try:
        raw      = base64.b64decode(resultado["data"])
        mimetype = resultado.get("mimetype", "image/jpeg")
        return send_file(BytesIO(raw), mimetype=mimetype)
    except Exception as e:
        logger.error("Error sirviendo imagen slug=%s campo=%s: %s", slug, campo, e)
        abort(500)
