"""
app/recuperacion/controller.py
──────────────────────────────
Lógica de negocio para recuperación de contraseña.
Canales soportados: email (Flask-Mail) y whatsapp (Twilio).
"""

import logging
import secrets
import os

from app.recuperacion.model import RecuperacionModel
from app.auth.model import SIGLAS_VALIDAS

logger = logging.getLogger(__name__)


class RecuperacionController:

    @staticmethod
    def solicitar_recuperacion(tipo_doc, num_doc, email):
        """
        Valida que el usuario exista con ese tipo_doc + num_doc + email.
        Genera un token de recuperación y lo guarda en MongoDB.
        Retorna (True, {"token": ..., "usuario": ...}) o (False, mensaje_error).
        """
        logger.info("Solicitud de recuperación: tipo=%s num=%s email=%s", tipo_doc, num_doc, email)

        if not tipo_doc or tipo_doc not in SIGLAS_VALIDAS:
            return False, "Tipo de documento no válido"

        if not num_doc:
            return False, "Número de documento requerido"

        if not email or "@" not in email:
            return False, "Correo electrónico no válido"

        usuario = RecuperacionModel.buscar_por_documento_y_email(tipo_doc, num_doc, email)

        if not usuario:
            logger.warning("Usuario no encontrado: tipo=%s num=%s", tipo_doc, num_doc)
            return False, "No encontramos una cuenta con esos datos"

        if not usuario.get("activo"):
            logger.warning("Cuenta inactiva: num=%s", num_doc)
            return False, "Cuenta inactiva. Contacte al administrador"

        token = secrets.token_urlsafe(32)
        RecuperacionModel.guardar_token(num_doc, token)
        logger.info("Token generado para num_doc=%s", num_doc)

        return True, {"token": token, "usuario": usuario}

    # ── DESPACHO DE CANAL ──────────────────────────────────────────────────

    @staticmethod
    def enviar_por_canal(canal, destino, enlace):
        """
        Envía el enlace de recuperación por el canal elegido.

        Args:
            canal   : "email" o "whatsapp"
            destino : dirección email o número de teléfono
            enlace  : URL completa del restablecimiento

        Retorna (True, None) o (False, mensaje_error).
        """
        logger.info("Enviando por canal='%s' a destino='%s'", canal, destino)

        if canal == "whatsapp":
            return RecuperacionController._enviar_whatsapp(destino, enlace)
        else:
            return RecuperacionController._enviar_email(destino, enlace)

    # ── EMAIL ──────────────────────────────────────────────────────────────

    @staticmethod
    def _enviar_email(email_destino, enlace):
        """Envía el correo de recuperación con Flask-Mail."""
        try:
            from app import mail
            from flask_mail import Message

            logger.info("Enviando email a %s", email_destino)

            msg = Message(
                subject="🔐 Recuperación de contraseña — Nidus",
                recipients=[email_destino],
                html=f"""
                <div style="font-family: 'Segoe UI', sans-serif; max-width: 520px; margin: auto;
                            background: #0d1a5a; color: white; border-radius: 16px;
                            padding: 32px; text-align: center;">
                    <h2 style="color:#00d4ff; margin-bottom: 8px;">Recuperación de contraseña</h2>
                    <p style="color:rgba(255,255,255,0.7); margin-bottom: 28px;">
                        Haz clic en el botón para crear tu nueva contraseña.<br>
                        <small>Este enlace expira en <strong>30 minutos</strong>.</small>
                    </p>
                    <a href="{enlace}"
                       style="display:inline-block; padding: 14px 36px;
                              background: linear-gradient(135deg,#00d4ff,#e600ff);
                              color: white; font-weight: 700; border-radius: 10px;
                              text-decoration: none; letter-spacing: 1px; font-size: 0.95rem;">
                        Restablecer contraseña
                    </a>
                    <p style="margin-top: 24px; color: rgba(255,255,255,0.4); font-size: 0.75rem;">
                        Si no solicitaste este cambio, ignora este mensaje.<br>
                        Nidus — Nidus Tecnología y Soluciones S.A.S
                    </p>
                </div>
                """
            )
            mail.send(msg)
            logger.info("Email enviado exitosamente a %s", email_destino)
            return True, None

        except Exception as e:
            logger.error("ERROR al enviar email a %s: %s", email_destino, str(e), exc_info=True)
            return False, str(e)

    # ── WHATSAPP ───────────────────────────────────────────────────────────

    @staticmethod
    def _enviar_whatsapp(telefono_destino, enlace):
        """Envía mensaje de recuperación por WhatsApp usando Twilio."""
        try:
            from twilio.rest import Client
            from twilio.base.exceptions import TwilioRestException

            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token  = os.environ.get("TWILIO_AUTH_TOKEN")
            from_number = os.environ.get("TWILIO_WHATSAPP_FROM")  # 'whatsapp:+1XXXXXXXXXX'

            if not all([account_sid, auth_token, from_number]):
                logger.error("Credenciales de Twilio incompletas en variables de entorno")
                return False, "Configuración de WhatsApp incompleta en el servidor"

            # Limpiar número: solo dígitos
            num_solo_digitos = ''.join(filter(str.isdigit, str(telefono_destino)))

            if not num_solo_digitos:
                logger.error("Número de teléfono vacío o inválido: '%s'", telefono_destino)
                return False, "Número de teléfono inválido"

            # Formato Colombia: si tiene 10 dígitos, agregar prefijo 57
            if len(num_solo_digitos) == 10:
                num_solo_digitos = "57" + num_solo_digitos

            to_number = f"whatsapp:+{num_solo_digitos}"
            logger.info("Enviando WhatsApp a %s (desde %s)", to_number, from_number)

            client = Client(account_sid, auth_token)
            message = client.messages.create(
                from_=from_number,
                to=to_number,
                body=(
                    f"🔐 *Nidus — Restablece tu contraseña*\n\n"
                    f"Recibiste este mensaje porque solicitaste un cambio de contraseña.\n\n"
                    f"👇 Toca el enlace para continuar:\n"
                    f"{enlace}\n\n"
                    f"⏱ Expira en *30 minutos*.\n"
                    f"Si no lo solicitaste, ignora este mensaje."
                )
            )
            logger.info("WhatsApp enviado. SID: %s", message.sid)
            return True, None

        except TwilioRestException as e:
            logger.error("TwilioRestException (code=%s): %s", e.code, e.msg)
            return False, f"Error de Twilio ({e.code}): {e.msg}"
        except Exception as e:
            logger.error("Error inesperado enviando WhatsApp: %s", str(e), exc_info=True)
            return False, str(e)

    # ── VALIDACIÓN Y CAMBIO DE CONTRASEÑA ─────────────────────────────────

    @staticmethod
    def validar_token(token):
        """Verifica que el token sea válido y no haya expirado."""
        logger.info("Validando token de recuperación")
        usuario, error = RecuperacionModel.buscar_por_token(token)
        if error:
            logger.warning("Token inválido o expirado: %s", error)
            return False, error
        return True, usuario["numero_documento"]

    @staticmethod
    def cambiar_password(token, nueva_password, confirmar_password):
        """Valida y aplica el cambio de contraseña."""
        if not nueva_password or len(nueva_password) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres"

        if nueva_password != confirmar_password:
            return False, "Las contraseñas no coinciden"

        usuario, error = RecuperacionModel.buscar_por_token(token)
        if error:
            logger.warning("Cambio de contraseña fallido: %s", error)
            return False, error

        RecuperacionModel.cambiar_password(usuario["numero_documento"], nueva_password)
        logger.info("Contraseña cambiada para num_doc=%s", usuario["numero_documento"])
        return True, "Contraseña actualizada correctamente"