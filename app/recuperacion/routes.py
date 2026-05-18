"""
app/recuperacion/routes.py
──────────────────────────
Rutas del flujo de recuperación de contraseña.

Flujo completo:
  GET  /recuperar-contrasena/           → formulario de solicitud
  POST /recuperar-contrasena/           → valida usuario, genera token, envía enlace
  GET  /recuperar-contrasena/nueva/<t>  → formulario de nueva contraseña
  POST /recuperar-contrasena/nueva/<t>  → aplica el cambio y redirige al login
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for
from app.recuperacion.controller import RecuperacionController

logger = logging.getLogger(__name__)

recuperacion_bp = Blueprint("recuperacion", __name__, url_prefix="/recuperar-contrasena")


def _enmascarar_email(email: str) -> str:
    if not email or "@" not in email:
        return "***@***.***"
    local, domain = email.split("@", 1)
    local_mask = (local[:2] + "***") if len(local) > 2 else (local[0] + "***")
    partes = domain.split(".")
    domain_mask = partes[0][:1] + "***." + ".".join(partes[1:])
    return f"{local_mask}@{domain_mask}"


def _enmascarar_telefono(telefono: str) -> str:
    digits = "".join(filter(str.isdigit, str(telefono)))
    if len(digits) >= 4:
        return "*** *** " + digits[-4:]
    return "***"


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


# ── Verificación previa (AJAX) ─────────────────────────────────────────────

@recuperacion_bp.route("/verificar", methods=["POST"])
def verificar_usuario():
    """Valida el usuario y devuelve sus datos de contacto enmascarados (JSON)."""
    from flask import jsonify
    from app.recuperacion.model import RecuperacionModel

    tipo_doc = request.form.get("tipoDoc", "").strip()
    num_doc  = request.form.get("numDoc",  "").strip()
    email    = request.form.get("correo",  "").strip()

    if not tipo_doc or not num_doc or not email or "@" not in email:
        return jsonify({"ok": False, "error": "Completa todos los campos."})

    usuario = RecuperacionModel.buscar_por_documento_y_email(tipo_doc, num_doc, email)

    if not usuario:
        return jsonify({"ok": False, "error": "No encontramos una cuenta con esos datos."})

    if not usuario.get("activo"):
        return jsonify({"ok": False, "error": "Cuenta inactiva. Contacte al administrador."})

    tel_real = (usuario.get("telefono") or "").strip()
    return jsonify({
        "ok":             True,
        "email_mask":     _enmascarar_email(usuario.get("email", "")),
        "telefono_mask":  _enmascarar_telefono(tel_real) if tel_real else None,
        "tiene_telefono": bool(tel_real),
    })


# ── Solicitud de recuperación ──────────────────────────────────────────────

@recuperacion_bp.route("/", methods=["GET"])
def recuperar_get():
    return render_template("recuperacion/recuperar.html", tipos_doc=_tipos_documento())


@recuperacion_bp.route("/", methods=["POST"])
def recuperar_post():
    tipo_doc = request.form.get("tipoDoc", "").strip()
    num_doc  = request.form.get("numDoc",  "").strip()
    email    = request.form.get("correo",  "").strip()
    canal    = request.form.get("canal",   "").strip().lower()

    logger.info("Solicitud recuperación: tipo=%s num=%s canal=%s", tipo_doc, num_doc, canal)

    # ── Validar que el usuario eligió un canal ─────────────────────────────
    if canal not in ("email", "whatsapp"):
        logger.warning("Canal inválido o no seleccionado: '%s'", canal)
        return render_template(
            "recuperacion/recuperar.html",
            error="Debes elegir un canal de envío (correo o WhatsApp).",
            tipos_doc=_tipos_documento(),
            form_data=request.form
        )

    # ── Buscar usuario y generar token ─────────────────────────────────────
    exito, resultado = RecuperacionController.solicitar_recuperacion(tipo_doc, num_doc, email)

    if not exito:
        logger.warning("Recuperación fallida: %s", resultado)
        return render_template(
            "recuperacion/recuperar.html",
            error=resultado,
            tipos_doc=_tipos_documento(),
            form_data=request.form
        )

    token   = resultado["token"]
    usuario = resultado["usuario"]
    enlace  = url_for("recuperacion.nueva_password_get", token=token, _external=True)

    # ── Seleccionar destino según canal ────────────────────────────────────
    if canal == "whatsapp":
        destino = usuario.get("telefono", "").strip()
        if not destino:
            logger.warning("No hay teléfono registrado para num=%s", num_doc)
            return render_template(
                "recuperacion/recuperar.html",
                error="No tienes un número de teléfono registrado. Usa el canal de correo.",
                tipos_doc=_tipos_documento(),
                form_data=request.form
            )
    else:
        destino = email

    # ── Enviar por el canal elegido ────────────────────────────────────────
    enviado, msg_envio = RecuperacionController.enviar_por_canal(canal, destino, enlace)

    if not enviado:
        logger.error("Fallo al enviar por canal=%s: %s", canal, msg_envio)
        return render_template(
            "recuperacion/recuperar.html",
            error=f"No se pudo enviar el enlace: {msg_envio}",
            tipos_doc=_tipos_documento(),
            form_data=request.form
        )

    exito_msg = (
        "¡Enlace enviado por WhatsApp! Revisa tus mensajes."
        if canal == "whatsapp"
        else "¡Enlace enviado al correo! Revisa tu bandeja de entrada."
    )
    logger.info("Enlace de recuperación enviado por %s a %s", canal, destino)
    return render_template("recuperacion/recuperar.html", exito=True, exito_msg=exito_msg)


# ── Formulario de nueva contraseña ─────────────────────────────────────────

@recuperacion_bp.route("/nueva/<token>", methods=["GET"])
def nueva_password_get(token):
    """Valida el token y muestra el formulario para crear nueva contraseña."""
    logger.info("Acceso a formulario nueva contraseña (token=%s...)", token[:8])
    valido, resultado = RecuperacionController.validar_token(token)
    if not valido:
        logger.warning("Token inválido en GET: %s", resultado)
        return render_template("recuperacion/recuperar.html",
                               error=resultado,
                               tipos_doc=_tipos_documento())
    return render_template("recuperacion/nueva_contrasena.html", token=token)


@recuperacion_bp.route("/nueva/<token>", methods=["POST"])
def nueva_password_post(token):
    """Aplica el cambio de contraseña y redirige al login si fue exitoso."""
    nueva    = request.form.get("password",  "")
    confirma = request.form.get("confirmar", "")

    logger.info("Intento de cambio de contraseña (token=%s...)", token[:8])

    exito, mensaje = RecuperacionController.cambiar_password(token, nueva, confirma)

    if exito:
        logger.info("Contraseña cambiada exitosamente")
        return render_template("recuperacion/nueva_contrasena.html",
                               token=token, cambio_exitoso=True)

    logger.warning("Cambio de contraseña fallido: %s", mensaje)
    return render_template(
        "recuperacion/nueva_contrasena.html",
        error=mensaje,
        token=token
    )