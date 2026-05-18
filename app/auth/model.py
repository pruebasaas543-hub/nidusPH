"""
app/auth/model.py
"""

from app import db
from datetime import datetime
import bcrypt

# ── CATÁLOGO OFICIAL DE TIPOS DE DOCUMENTO ──────────────────────────────────
# Fallback hardcodeado; se sobreescribe en tiempo de inicio desde MongoDB.
TIPOS_DOCUMENTO = {
    "CC":  {"codigo_dian": 13, "nombre": "Cédula de Ciudadanía",           "tipo_persona": "Natural"},
    "TI":  {"codigo_dian": 12, "nombre": "Tarjeta de Identidad",           "tipo_persona": "Natural"},
    "RC":  {"codigo_dian": 11, "nombre": "Registro Civil",                 "tipo_persona": "Natural"},
    "CE":  {"codigo_dian": 22, "nombre": "Cédula de Extranjería",          "tipo_persona": "Natural"},
    "PA":  {"codigo_dian": 41, "nombre": "Pasaporte",                      "tipo_persona": "Natural"},
    "PPT": {"codigo_dian": 47, "nombre": "Permiso Protección Temporal",    "tipo_persona": "Natural"},
    "TE":  {"codigo_dian": 21, "nombre": "Tarjeta de Extranjería",         "tipo_persona": "Natural"},
    "PEP": {"codigo_dian": 48, "nombre": "Permiso Especial Permanencia",   "tipo_persona": "Natural"},
    "SC":  {"codigo_dian": 50, "nombre": "Salvoconducto",                  "tipo_persona": "Natural"},
    "CD":  {"codigo_dian": 44, "nombre": "Carné Diplomático",              "tipo_persona": "Natural"},
    "NIT": {"codigo_dian": 31, "nombre": "Núm. Identificación Tributaria", "tipo_persona": "Juridica"},
}

SIGLAS_VALIDAS = list(TIPOS_DOCUMENTO.keys())


def reload_tipos_documento():
    """Recarga TIPOS_DOCUMENTO y SIGLAS_VALIDAS desde MongoDB en tiempo de inicio.
    Muta los objetos en lugar de reasignarlos para que los módulos que ya
    importaron las referencias vean los valores actualizados.
    """
    try:
        docs = list(db["tipo_identificador_fiscal"].find(
            {}, {"_id": 0, "id_sigla": 1, "codigo_dian": 1, "nombre": 1, "tipo_persona": 1}
        ))
        if docs:
            nuevos = {
                d["id_sigla"]: {
                    "codigo_dian":  d.get("codigo_dian"),
                    "nombre":       d.get("nombre", ""),
                    "tipo_persona": d.get("tipo_persona", "Natural"),
                }
                for d in docs if d.get("id_sigla")
            }
            TIPOS_DOCUMENTO.clear()
            TIPOS_DOCUMENTO.update(nuevos)
            SIGLAS_VALIDAS.clear()
            SIGLAS_VALIDAS.extend(TIPOS_DOCUMENTO.keys())
    except Exception:
        pass  # mantiene el fallback hardcodeado si la colección no existe aún


def get_collection():
    """Obtiene la colección en el momento de uso, no al importar."""
    return db["users"]


class UserModel:

    @staticmethod
    def crear_usuario(tipo_doc, num_doc, password, rol=None,
                      nombres="", apellidos="", email="", telefono="",
                      conjunto_id=None, creado_por=None):
        """Crea un usuario nuevo en MongoDB con contraseña encriptada."""

        # Validar tipo de documento antes de guardar
        if tipo_doc not in SIGLAS_VALIDAS:
            raise ValueError(f"Tipo de documento '{tipo_doc}' no válido. "
                             f"Permitidos: {SIGLAS_VALIDAS}")

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        usuario = {
            # ── IDENTIFICACIÓN ──────────────────────────
            "tipo_documento":       tipo_doc,
            "numero_documento":     num_doc,

            # ── SEGURIDAD ───────────────────────────────
            "password":             hashed,
            "intentos_fallidos":    0,
            "bloqueado_hasta":      None,
            "token_recuperacion":   None,
            "token_expira":         None,

            # ── DATOS PERSONALES ────────────────────────
            "nombres":              nombres,
            "apellidos":            apellidos,
            "email":                email,
            "telefono":             telefono,

            # ── AUDITORÍA ───────────────────────────────
            "activo":               True,
            "primer_login":         True,
            "creado_en":            datetime.utcnow(),
            "creado_por":           creado_por,
            "ultimo_login":         None,
            "ultima_actualizacion": None,
        }

        resultado = get_collection().insert_one(usuario)
        return str(resultado.inserted_id)

    @staticmethod
    def buscar_por_documento(tipo_doc, num_doc):
        """Busca usuario por tipo y número de documento."""
        return get_collection().find_one({
            "tipo_documento":   tipo_doc,
            "numero_documento": num_doc
        })

    @staticmethod
    def verificar_password(password_plano, password_hash):
        """Compara contraseña ingresada con el hash guardado en MongoDB."""
        return bcrypt.checkpw(password_plano.encode("utf-8"), password_hash)

    @staticmethod
    def actualizar_campos(num_doc, campos: dict):
        """Actualiza campos específicos de un usuario."""
        campos["ultima_actualizacion"] = datetime.utcnow()
        get_collection().update_one(
            {"numero_documento": num_doc},
            {"$set": campos}
        )

    @staticmethod
    def registrar_ultimo_login(num_doc):
        """
        Siempre guarda la fecha y hora exacta del último login exitoso.
        Se llama desde el controller tras verificar credenciales correctas.
        """
        get_collection().update_one(
            {"numero_documento": num_doc},
            {
                "$set": {
                    "ultimo_login":          datetime.utcnow(),
                    "intentos_fallidos":     0,       # resetear intentos
                    "bloqueado_hasta":       None,     # quitar bloqueo si existía
                    "ultima_actualizacion":  datetime.utcnow()
                }
            }
        )