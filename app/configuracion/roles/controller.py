"""
app/configuracion/roles/controller.py
"""

from app.configuracion.roles.model import RolModel, HabilitacionRolModel


def _ids_servicios_activos() -> list:
    from app.servicios.model import ServicioModel
    return [str(s["_id"]) for s in ServicioModel.listar(solo_activos=True)]


class RolController:

    @staticmethod
    def listar(solo_activos=True, excluir_internos=False):
        return True, RolModel.listar(solo_activos=solo_activos, excluir_internos=excluir_internos)

    @staticmethod
    def crear(datos: dict, creado_por: str):
        nombre  = datos.get("nombre", "").strip()
        modulos = datos.get("modulos", [])

        if not nombre:
            return False, "El nombre es obligatorio"
        if RolModel.buscar_por_nombre(nombre):
            return False, f"Ya existe el rol '{nombre}'"

        ids_validos = _ids_servicios_activos()
        invalidos = [m for m in modulos if m not in ids_validos]
        if invalidos:
            return False, f"Módulos no válidos: {invalidos}"

        rol_id = RolModel.crear(datos, creado_por)
        return True, {"rol_id": rol_id, "mensaje": "Rol creado correctamente"}

    @staticmethod
    def editar(rol_id: str, datos: dict):
        rol = RolModel.buscar_por_id(rol_id)
        if not rol:
            return False, "Rol no encontrado"

        if "modulos" in datos:
            modulos = datos.get("modulos", [])
            ids_validos = _ids_servicios_activos()
            invalidos = [m for m in modulos if m not in ids_validos]
            if invalidos:
                return False, f"Módulos no válidos: {invalidos}"

        RolModel.actualizar(rol_id, datos)
        return True, "Rol actualizado"

    @staticmethod
    def eliminar(rol_id: str):
        if not RolModel.eliminar(rol_id):
            return False, "No se puede eliminar un rol del sistema"
        return True, "Rol eliminado"


class HabilitacionRolController:

    @staticmethod
    def obtener(empresa_id: str):
        from app.configuracion.empresas.model import EmpresaModel
        empresa = EmpresaModel.buscar_por_id(empresa_id)
        if not empresa:
            return False, "Empresa no encontrada"
        HabilitacionRolModel.migrar_roles_activos_a_ids()
        config = HabilitacionRolModel.obtener_para_empresa(empresa_id)
        return True, {
            "empresa":        empresa,
            "todos_roles":    RolModel.listar(excluir_internos=True),
            "roles_activos":  config.get("roles_activos", []) if config else [],
            "creado_en":         config.get("creado_en")           if config else None,
            "actualizado_en":    config.get("actualizado_en")      if config else None,
            "id_actualizado_por":config.get("id_actualizado_por","") if config else "",
        }

    @staticmethod
    def guardar(empresa_id: str, roles_activos: list, usuario_id: str = ""):
        from app.configuracion.empresas.model import EmpresaModel
        if not EmpresaModel.buscar_por_id(empresa_id):
            return False, "Empresa no encontrada"
        ids_validos = {str(r["_id"]) for r in RolModel.listar(solo_activos=False, excluir_internos=True)}
        invalidos = [r for r in roles_activos if r not in ids_validos]
        if invalidos:
            return False, f"Roles no reconocidos: {invalidos}"
        HabilitacionRolModel.guardar(empresa_id, roles_activos, usuario_id)
        return True, "Habilitación guardada"
