"""
app/configuracion/planes/controller.py
"""

from app.configuracion.planes.model import PlanModel


def _ids_servicios_activos() -> list:
    from app.servicios.model import ServicioModel
    return [str(s["_id"]) for s in ServicioModel.listar(solo_activos=True)]


class PlanController:

    @staticmethod
    def listar(solo_activos=False):
        return True, PlanModel.listar(solo_activos=solo_activos)

    @staticmethod
    def obtener(plan_id: str):
        plan = PlanModel.buscar_por_id(plan_id)
        if not plan: return False, "Plan no encontrado"
        return True, plan

    @staticmethod
    def crear(datos: dict, creado_por: str):
        nombre = datos.get("nombre", "").strip()
        if not nombre:
            return False, "El nombre es obligatorio"

        modulos = datos.get("modulos_incluidos", [])
        if not isinstance(modulos, list):
            return False, "modulos_incluidos debe ser una lista"
        ids_validos = _ids_servicios_activos()
        invalidos = [m for m in modulos if m not in ids_validos]
        if invalidos:
            return False, f"Módulos no válidos: {invalidos}"

        limites = datos.get("limites", {})
        if not isinstance(limites, dict):
            return False, "limites debe ser un objeto"

        soporte = limites.get("soporte", [])
        if not isinstance(soporte, list):
            return False, "limites.soporte debe ser una lista"

        precio = datos.get("precio", {})
        if not isinstance(precio, dict):
            return False, "precio debe ser un objeto"

        pid = PlanModel.crear(datos, creado_por)
        return True, {"id": pid, "mensaje": "Plan creado correctamente"}

    @staticmethod
    def editar(plan_id: str, datos: dict):
        plan = PlanModel.buscar_por_id(plan_id)
        if not plan:
            return False, "Plan no encontrado"

        if "modulos_incluidos" in datos:
            modulos = datos["modulos_incluidos"]
            if not isinstance(modulos, list):
                return False, "modulos_incluidos debe ser una lista"
            ids_validos = _ids_servicios_activos()
            invalidos = [m for m in modulos if m not in ids_validos]
            if invalidos:
                return False, f"Módulos no válidos: {invalidos}"

        if "limites" in datos and "soporte" in datos["limites"]:
            if not isinstance(datos["limites"]["soporte"], list):
                return False, "limites.soporte debe ser una lista"

        PlanModel.actualizar(plan_id, datos)
        return True, "Plan actualizado correctamente"

    @staticmethod
    def archivar(plan_id: str):
        plan = PlanModel.buscar_por_id(plan_id)
        if not plan:
            return False, "Plan no encontrado"
        PlanModel.eliminar(plan_id)
        return True, "Plan eliminado"

    @staticmethod
    def modulos_habilitados_por_empresa(empresa_id: str) -> list:
        from app.configuracion.empresas.model import EmpresaModel
        empresa = EmpresaModel.buscar_por_id(empresa_id)
        if not empresa:
            return []
        plan_id_str = empresa.get("plan", "")
        return PlanModel.modulos_de_plan(plan_id_str)
