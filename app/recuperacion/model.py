"""
app/recuperacion/model.py
"""

from app import db
from datetime import datetime, timedelta
import bcrypt

def get_collection():
    return db["users"]

class RecuperacionModel:
    @staticmethod
    def buscar_por_documento_y_email(tipo_doc, num_doc, email):
        """Busca usuario y retorna el documento completo (incluyendo teléfono)."""
        return get_collection().find_one({
            "tipo_documento": tipo_doc,
            "numero_documento": num_doc,
            "email": email.strip().lower()
        })

    @staticmethod
    def guardar_token(num_doc, token):
        """Guarda el token con expiración."""
        get_collection().update_one(
            {"numero_documento": num_doc},
            {"$set": {
                "token_recuperacion": token,
                "token_expira": datetime.utcnow() + timedelta(minutes=30),
                "ultima_actualizacion": datetime.utcnow()
            }}
        )

    @staticmethod
    def buscar_por_token(token):
        """Busca y valida la vigencia del token."""
        usuario = get_collection().find_one({"token_recuperacion": token})
        if not usuario:
            return None, "Este enlace ya no es válido. Pudo haber sido reemplazado por una solicitud más reciente o ya fue utilizado."

        if datetime.utcnow() > usuario.get("token_expira", datetime.utcnow()):
            return None, "El enlace ha expirado. Solicita uno nuevo."

        return usuario, None

    @staticmethod
    def cambiar_password(num_doc, nueva_password):
        """Actualiza password y limpia los campos de recuperación."""
        hashed = bcrypt.hashpw(nueva_password.encode("utf-8"), bcrypt.gensalt())
        get_collection().update_one(
            {"numero_documento": num_doc},
            {"$set": {
                "password":             hashed,
                "token_recuperacion":   None,
                "token_expira":         None,
                "intentos_fallidos":    0,
                "bloqueado_hasta":      None,
                "primer_login":         False,
                "ultima_actualizacion": datetime.utcnow()
            }}
        )