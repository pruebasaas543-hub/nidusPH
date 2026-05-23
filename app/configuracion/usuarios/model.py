"""
app/configuracion/usuarios/model.py
"""

from app import db
from datetime import datetime
from bson import ObjectId
import bcrypt


def _col(): return db["users"]


def _roles_sistema():
    from app.configuracion.roles.model import RolModel
    return RolModel.nombres_sistema()


class UsuarioConfigModel:

    CAMPOS_EDITABLES = {
        "nombres", "apellidos", "email", "telefono", "activo",
        "nombre_contacto_emergencia", "telefono_contacto_emergencia",
    }

    @staticmethod
    def listar(solo_activos=False):
        from app import db
        filtro = {}
        if solo_activos:
            filtro["activo"] = True
        pipeline = [
            {"$match": filtro},
            {"$project": {
                "password": 0, "token_recuperacion": 0,
                "bloqueado_hasta": 0, "intentos_fallidos": 0, "token_expira": 0,
            }},
            {"$lookup": {
                "from": "asociaciones",
                "let": {"uid": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$and": [
                        {"$eq": ["$user_id", "$$uid"]},
                        {"$eq": ["$activo", True]},
                    ]}}},
                    {"$lookup": {
                        "from": "empresas",
                        "localField": "empresa_id",
                        "foreignField": "_id",
                        "as": "emp",
                    }},
                    {"$unwind": {"path": "$emp", "preserveNullAndEmptyArrays": True}},
                    {"$addFields": {
                        "_rol_oid": {"$cond": [
                            {"$regexMatch": {"input": {"$ifNull": ["$rol_asignado", ""]}, "regex": "^[0-9a-f]{24}$"}},
                            {"$toObjectId": "$rol_asignado"},
                            None,
                        ]},
                    }},
                    {"$lookup": {
                        "from": "roles",
                        "localField": "_rol_oid",
                        "foreignField": "_id",
                        "as": "_rol_doc",
                    }},
                    {"$project": {
                        "_id": 0,
                        "empresa_id":     1,
                        "empresa_nombre": "$emp.razon_social",
                        "rol_asignado":   1,
                        "rol_nombre": {"$ifNull": [
                            {"$arrayElemAt": ["$_rol_doc.nombre", 0]},
                            "$rol_asignado",
                        ]},
                    }},
                ],
                "as": "asociaciones",
            }},
            {"$sort": {"nombres": 1}},
        ]
        return list(db["users"].aggregate(pipeline))

    @staticmethod
    def buscar_por_id(user_id):
        try:
            return _col().find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None

    @staticmethod
    def buscar_por_documento(tipo_doc, num_doc):
        return _col().find_one({"tipo_documento": tipo_doc, "numero_documento": num_doc})

    @staticmethod
    def es_usuario_sistema(user_id: str) -> bool:
        """True si el usuario tiene una asociación de sistema (empresa_id: null)."""
        try:
            return db["asociaciones"].find_one({
                "user_id": ObjectId(user_id),
                "empresa_id": None,
                "activo": True,
            }) is not None
        except Exception:
            return False

    @staticmethod
    def actualizar(user_id: str, datos: dict):
        update = {}
        for k, v in datos.items():
            if k not in UsuarioConfigModel.CAMPOS_EDITABLES:
                continue
            # No sobreescribir con cadena vacía campos obligatorios
            if k in ("nombres", "apellidos", "email") and (v is None or str(v).strip() == ""):
                continue
            update[k] = v
        if not update:
            return
        update["ultima_actualizacion"] = datetime.utcnow()
        _col().update_one({"_id": ObjectId(user_id)}, {"$set": update})

    @staticmethod
    def cambiar_estado(user_id: str, activo: bool):
        _col().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"activo": activo, "ultima_actualizacion": datetime.utcnow()}}
        )

    @staticmethod
    def resetear_password(user_id: str, nueva_password: str):
        hashed = bcrypt.hashpw(nueva_password.encode("utf-8"), bcrypt.gensalt())
        _col().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "password":             hashed,
                "primer_login":         True,
                "intentos_fallidos":    0,
                "bloqueado_hasta":      None,
                "ultima_actualizacion": datetime.utcnow(),
            }}
        )

    @staticmethod
    def eliminar(user_id: str):
        _col().delete_one({"_id": ObjectId(user_id)})

    @staticmethod
    def normalizar_schema() -> int:
        """Agrega campos faltantes al esquema limpio. Idempotente."""
        defaults = {
            "tipo_documento":               "",
            "numero_documento":             "",
            "nombres":                      "",
            "apellidos":                    "",
            "email":                        "",
            "telefono":                     "",
            "nombre_contacto_emergencia":   "",
            "telefono_contacto_emergencia": "",
            "intentos_fallidos":            0,
            "bloqueado_hasta":              None,
            "token_recuperacion":           None,
            "token_expira":                 None,
            "activo":                       True,
            "primer_login":                 True,
            "creado_en":                    None,
            "creado_por":                   None,
            "ultimo_login":                 None,
            "ultima_actualizacion":         None,
        }
        modificados = 0
        for doc in _col().find({}):
            faltantes = {k: v for k, v in defaults.items() if k not in doc}
            if faltantes:
                _col().update_one({"_id": doc["_id"]}, {"$set": faltantes})
                modificados += 1
        return modificados

    @staticmethod
    def migrar_a_esquema_limpio() -> dict:
        """
        Migración completa al esquema limpio:
        1. Crea asociaciones de sistema para SuperAdmin/ImplementadorNidus
        2. Normaliza asociaciones existentes con nuevos campos
        3. Hace $unset de campos removidos en users
        Idempotente.
        """
        col_users = db["users"]
        col_asoc  = db["asociaciones"]

        # 1. Crear asociaciones de sistema para usuarios con rol en users (legado)
        asoc_creadas = 0
        for user in col_users.find({"rol": {"$in": list(_roles_sistema())}}):
            ya_existe = col_asoc.find_one({
                "user_id":    user["_id"],
                "empresa_id": None,
                "activo":     True,
            })
            if not ya_existe:
                col_asoc.insert_one({
                    "user_id":                      user["_id"],
                    "empresa_id":                   None,
                    "rol_asignado":                 user["rol"],
                    "unidad":                       "",
                    "torre":                        "",
                    "apartamento":                  "",
                    "nombre_contacto_emergencia":   "",
                    "telefono_contacto_emergencia": "",
                    "activo":                       True,
                    "creado_en":                    datetime.utcnow(),
                    "creado_por":                   "migracion",
                })
                asoc_creadas += 1

        # 2. Normalizar asociaciones con campos nuevos
        campos_asoc = {
            "torre":                        "",
            "apartamento":                  "",
            "nombre_contacto_emergencia":   "",
            "telefono_contacto_emergencia": "",
        }
        asoc_normalizadas = 0
        for doc in col_asoc.find({}):
            faltantes = {k: v for k, v in campos_asoc.items() if k not in doc}
            if faltantes:
                col_asoc.update_one({"_id": doc["_id"]}, {"$set": faltantes})
                asoc_normalizadas += 1

        # 3. $unset campos removidos de users
        campos_unset = {
            "codigo_dian":                  "",
            "tipo_persona":                 "",
            "rol":                          "",
            "conjunto_id":                  "",
            "torre":                        "",
            "apartamento":                  "",
            "nombre_contacto_emergencia":   "",
            "telefono_contacto_emergencia": "",
            "empresa_inactiva":             "",
        }
        res = col_users.update_many({}, {"$unset": campos_unset})

        return {
            "asoc_sistema_creadas": asoc_creadas,
            "asoc_normalizadas":    asoc_normalizadas,
            "users_actualizados":   res.modified_count,
        }
