"""
app/configuracion/usuarios/controller.py
"""

from app.configuracion.usuarios.model import UsuarioConfigModel
from app.auth.model import UserModel, SIGLAS_VALIDAS
from app.configuracion.utils import email_ok


def _es_sistema(usuario: dict) -> bool:
    """Detecta usuario de sistema via asociaciones (empresa_id: null)."""
    return UsuarioConfigModel.es_usuario_sistema(str(usuario["_id"]))


class UsuarioController:

    @staticmethod
    def listar():
        return True, UsuarioConfigModel.listar()

    @staticmethod
    def crear(datos: dict, creado_por: str):
        tipo_doc  = datos.get("tipo_documento", "").strip().upper()
        num_doc   = datos.get("numero_documento", "").strip()
        nombres   = datos.get("nombres", "").strip()
        apellidos = datos.get("apellidos", "").strip()
        email     = datos.get("email", "").strip()

        if tipo_doc not in SIGLAS_VALIDAS:  return False, "Tipo de documento no válido"
        if not num_doc or len(num_doc) < 3: return False, "Número de documento inválido"
        if not nombres:                     return False, "El nombre es obligatorio"
        if not apellidos:                   return False, "El apellido es obligatorio"
        if not email or not email_ok(email):return False, "Correo no válido"

        if UsuarioConfigModel.buscar_por_documento(tipo_doc, num_doc):
            return False, f"Ya existe un usuario con {tipo_doc} {num_doc}"

        user_id = UserModel.crear_usuario(
            tipo_doc=tipo_doc, num_doc=num_doc, password=num_doc,
            nombres=nombres, apellidos=apellidos,
            email=email, telefono=datos.get("telefono", "").strip(),
            creado_por=creado_por,
        )
        return True, {"user_id": user_id, "mensaje": "Usuario creado correctamente"}

    @staticmethod
    def editar(user_id: str, datos: dict):
        usuario = UsuarioConfigModel.buscar_por_id(user_id)
        if not usuario:
            return False, "Usuario no encontrado"
        if _es_sistema(usuario):
            return False, "No se puede editar un usuario de sistema"
        email = datos.get("email", "").strip()
        if email and not email_ok(email):
            return False, "Correo no válido"
        UsuarioConfigModel.actualizar(user_id, datos)
        return True, "Usuario actualizado correctamente"

    @staticmethod
    def cambiar_estado(user_id: str, activo: bool):
        usuario = UsuarioConfigModel.buscar_por_id(user_id)
        if not usuario:
            return False, "Usuario no encontrado"
        if _es_sistema(usuario):
            return False, "No se puede cambiar el estado de un usuario de sistema"
        UsuarioConfigModel.cambiar_estado(user_id, activo)
        return True, "Estado actualizado"

    @staticmethod
    def resetear_password(user_id: str):
        usuario = UsuarioConfigModel.buscar_por_id(user_id)
        if not usuario:
            return False, "Usuario no encontrado"
        UsuarioConfigModel.resetear_password(user_id, usuario["numero_documento"])
        return True, "Contraseña reseteada. El usuario deberá cambiarla en su próximo login"

    @staticmethod
    def eliminar(user_id: str):
        from app import db
        from bson import ObjectId
        usuario = UsuarioConfigModel.buscar_por_id(user_id)
        if not usuario:
            return False, "Usuario no encontrado"
        if _es_sistema(usuario):
            return False, "No se puede eliminar un usuario de sistema"
        asocs_activas = db["asociaciones"].count_documents({
            "user_id": ObjectId(user_id), "activo": True, "empresa_id": {"$ne": None}
        })
        if asocs_activas:
            return False, f"El usuario tiene {asocs_activas} asociación(es) activa(s). Desvincúlalo de todas las empresas antes de eliminarlo."
        UsuarioConfigModel.eliminar(user_id)
        return True, "Usuario eliminado correctamente"

    @staticmethod
    def asignar_rol_sistema(user_id: str, rol_nombre: str, asignado_por: str):
        from app.configuracion.roles.model import RolModel
        from app import db
        from bson import ObjectId
        from datetime import datetime

        usuario = UsuarioConfigModel.buscar_por_id(user_id)
        if not usuario:
            return False, "Usuario no encontrado"

        rol = RolModel.buscar_por_nombre(rol_nombre)
        if not rol or not rol.get("es_sistema"):
            return False, f"'{rol_nombre}' no es un rol de sistema válido"

        ya_tiene = db["asociaciones"].find_one({
            "user_id": ObjectId(user_id), "empresa_id": None, "activo": True
        })
        if ya_tiene:
            if ya_tiene.get("rol_asignado") == rol_nombre:
                return False, f"El usuario ya tiene el rol '{rol_nombre}'"
            db["asociaciones"].update_one(
                {"_id": ya_tiene["_id"]},
                {"$set": {"rol_asignado": rol_nombre}}   # nombre, no ID
            )
            # Inactivar asociaciones de empresa (ya tiene acceso global)
            db["asociaciones"].update_many(
                {"user_id": ObjectId(user_id), "empresa_id": {"$ne": None}},
                {"$set": {"activo": False}}
            )
            return True, f"Rol de sistema actualizado a '{rol_nombre}'"

        db["asociaciones"].insert_one({
            "user_id":                      ObjectId(user_id),
            "empresa_id":                   None,
            "rol_asignado":                 rol_nombre,  # nombre, no ID
            "unidad":                       "",
            "torre":                        "",
            "apartamento":                  "",
            "nombre_contacto_emergencia":   "",
            "telefono_contacto_emergencia": "",
            "activo":                       True,
            "creado_en":                    datetime.utcnow(),
            "creado_por":                   asignado_por,
        })
        # Inactivar asociaciones de empresa (ya tiene acceso global)
        db["asociaciones"].update_many(
            {"user_id": ObjectId(user_id), "empresa_id": {"$ne": None}},
            {"$set": {"activo": False}}
        )
        return True, f"Rol de sistema '{rol_nombre}' asignado correctamente"

    @staticmethod
    def quitar_rol_sistema(user_id: str, asignado_por: str):
        from app import db
        from bson import ObjectId

        asoc = db["asociaciones"].find_one({
            "user_id": ObjectId(user_id), "empresa_id": None, "activo": True
        })
        if not asoc:
            return False, "El usuario no tiene rol de sistema"
        db["asociaciones"].delete_one({"_id": asoc["_id"]})
        # Reactivar asociaciones de empresa que tenía antes
        reactivadas = db["asociaciones"].update_many(
            {"user_id": ObjectId(user_id), "empresa_id": {"$ne": None}},
            {"$set": {"activo": True}}
        ).modified_count
        msg = "Rol de sistema removido"
        if reactivadas:
            msg += f". {reactivadas} asociación(es) de empresa reactivada(s)"
        return True, msg
