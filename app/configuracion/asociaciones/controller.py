"""
app/configuracion/asociaciones/controller.py
"""

from app.configuracion.asociaciones.model import AsociacionModel
from app.configuracion.roles.model import HabilitacionRolModel, RolModel


class AsociacionController:

    @staticmethod
    def listar_todas():
        return True, AsociacionModel.listar_todas()

    @staticmethod
    def listar_por_empresa(empresa_id: str):
        from app.configuracion.empresas.model import EmpresaModel
        if not EmpresaModel.buscar_por_id(empresa_id):
            return False, "Empresa no encontrada"
        return True, AsociacionModel.listar_por_empresa(empresa_id)

    @staticmethod
    def listar_usuarios_disponibles():
        return True, AsociacionModel.usuarios_sin_empresa()

    @staticmethod
    def vincular(datos: dict, creado_por: str):
        user_id    = datos.get("user_id", "").strip()
        empresa_id = datos.get("empresa_id", "").strip()
        rol_asig   = datos.get("rol_asignado", "").strip()
        unidad     = datos.get("unidad", "").strip()
        torre                        = datos.get("torre", "").strip()
        apartamento                  = datos.get("apartamento", "").strip()
        nombre_contacto_emergencia   = datos.get("nombre_contacto_emergencia", "").strip()
        telefono_contacto_emergencia = datos.get("telefono_contacto_emergencia", "").strip()

        if not user_id:    return False, "Seleccione un usuario"
        if not empresa_id: return False, "Seleccione una empresa"
        if not rol_asig:   return False, "Seleccione un rol"

        # rol_asig puede venir como ID (24 hex) o como nombre — normalizar a ID
        from app.configuracion.roles.model import RolModel
        from bson import ObjectId
        import re
        if re.match(r'^[0-9a-f]{24}$', rol_asig):
            rol_existe = RolModel.buscar_por_id(rol_asig)
        else:
            rol_existe = RolModel.buscar_por_nombre(rol_asig)
        if not rol_existe:
            return False, "El rol seleccionado no existe"
        if rol_existe.get("es_sistema"):
            return False, f"El rol '{rol_existe['nombre']}' es de sistema y no puede asignarse a una empresa"

        rol_nombre = rol_existe["nombre"]   # siempre nombre, nunca ID

        # Verificar que el usuario no es de sistema
        from app import db
        try:
            es_sistema = db["asociaciones"].find_one({
                "user_id": ObjectId(user_id), "empresa_id": None, "activo": True
            }) is not None
        except Exception:
            es_sistema = False
        if es_sistema:
            return False, "Los usuarios de sistema no pueden tener asociaciones a empresas"

        asoc_id = AsociacionModel.vincular(
            user_id, empresa_id, rol_nombre, unidad, creado_por,
            torre=torre, apartamento=apartamento,
            nombre_contacto_emergencia=nombre_contacto_emergencia,
            telefono_contacto_emergencia=telefono_contacto_emergencia,
        )
        return True, {"asoc_id": asoc_id, "mensaje": "Usuario vinculado correctamente"}

    @staticmethod
    def desvincular(asoc_id: str):
        AsociacionModel.desactivar(asoc_id)
        return True, "Vínculo eliminado"
