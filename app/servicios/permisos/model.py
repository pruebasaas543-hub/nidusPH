"""
app/servicios/permisos/model.py
Gestión de permisos granulares por rol y módulo.

Colección: permisos_rol
  Un documento por combinación empresa + rol + módulo.
  Las acciones posibles son: ver, crear, editar, eliminar.

Mapping visibilidad (hardcoded — los campos en contactos son fijos):
  Residente                    → es_visible_para_residentes
  Vigilancia                   → es_visible_para_seguridad
  Administrador de la Copropiedad → es_visible_para_administracion
"""

from app import db
from datetime import datetime
from bson import ObjectId


# Mapping rol nombre → campo de visibilidad en directorio_contactos
VISIBILIDAD_POR_ROL = {
    "Residente":                        "es_visible_para_residentes",
    "Vigilancia":                       "es_visible_para_seguridad",
    "Administrador de la Copropiedad":  "es_visible_para_administracion",
}

# Acciones que ofrece cada módulo en el panel de permisos.
ACCIONES_POR_MODULO = {
    "directorio":   ["ver", "crear", "editar", "eliminar"],
    "boton_panico": ["emergencia", "configuracion", "log"],
}
MODULOS_DISPONIBLES = list(ACCIONES_POR_MODULO.keys())

# Compatibilidad: acciones por defecto del directorio.
ACCIONES_DEFAULT = {"ver": False, "crear": False, "editar": False, "eliminar": False}


def _acciones_modulo(modulo: str) -> list:
    return ACCIONES_POR_MODULO.get(modulo, ["ver", "crear", "editar", "eliminar"])


def _default_modulo(modulo: str) -> dict:
    return {a: False for a in _acciones_modulo(modulo)}


def _col():
    return db["permisos_rol"]


class PermisosRolModel:

    @staticmethod
    def _q(empresa_id: str, rol_id: str, modulo: str) -> dict:
        return {
            "empresa_id": ObjectId(empresa_id),
            "rol_id":     ObjectId(rol_id),
            "modulo":     modulo,
        }

    @staticmethod
    def obtener(empresa_id: str, rol_id: str, modulo: str) -> dict:
        """Retorna las acciones del permiso para el módulo. Si no existe, todo en False."""
        default = _default_modulo(modulo)
        doc = _col().find_one(PermisosRolModel._q(empresa_id, rol_id, modulo))
        if not doc:
            return default
        guardadas = doc.get("acciones", {})
        # Asegura todas las claves esperadas por el módulo
        return {a: bool(guardadas.get(a, False)) for a in default}

    @staticmethod
    def obtener_por_empresa(empresa_id: str) -> list:
        """Retorna todos los permisos de una empresa, agrupados."""
        docs = list(_col().find({"empresa_id": ObjectId(empresa_id)}))
        return docs

    @staticmethod
    def guardar(empresa_id: str, rol_id: str, modulo: str, acciones: dict):
        """Crea o actualiza el permiso de un rol para un módulo."""
        acciones_clean = {
            accion: bool(acciones.get(accion, False))
            for accion in _acciones_modulo(modulo)
        }
        ahora = datetime.utcnow()
        _col().update_one(
            PermisosRolModel._q(empresa_id, rol_id, modulo),
            {
                "$set":         {"acciones": acciones_clean, "actualizado_en": ahora},
                "$setOnInsert": {
                    "empresa_id": ObjectId(empresa_id),
                    "rol_id":     ObjectId(rol_id),
                    "modulo":     modulo,
                    "creado_en":  ahora,
                },
            },
            upsert=True,
        )

    @staticmethod
    def obtener_para_sesion(empresa_id: str, rol_nombre: str, modulo: str) -> dict:
        """
        Resuelve los permisos usando el nombre del rol (como viene en sesión).
        Retorna dict de acciones. Si el rol no existe o no tiene permisos, todo False.
        """
        try:
            rol_doc = db["roles"].find_one({"nombre": rol_nombre})
            if not rol_doc:
                return _default_modulo(modulo)
            return PermisosRolModel.obtener(empresa_id, str(rol_doc["_id"]), modulo)
        except Exception:
            return _default_modulo(modulo)

    @staticmethod
    def campo_visibilidad(rol_nombre: str) -> str | None:
        """Retorna el campo de visibilidad en contactos para este rol, o None si no aplica."""
        return VISIBILIDAD_POR_ROL.get(rol_nombre)
