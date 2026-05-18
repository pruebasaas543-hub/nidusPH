"""
app/servicios/controller.py
"""

from app.servicios.model import ServicioModel


class ServicioController:

    @staticmethod
    def crear(datos: dict, creado_por: str):
        nombre = datos.get("nombre", "").strip()
        if not nombre:
            return False, "El nombre del servicio es obligatorio"
        codigo = datos.get("codigo", nombre.lower().replace(" ", "_").replace("-", "_"))
        if ServicioModel.buscar_por_codigo(codigo):
            return False, f"Ya existe un servicio con el código '{codigo}'"
        datos["codigo"] = codigo
        _id = ServicioModel.crear(datos, creado_por)
        return True, _id

    @staticmethod
    def listar(solo_activos: bool = True):
        try:
            return True, ServicioModel.listar(solo_activos)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def obtener(servicio_id: str):
        doc = ServicioModel.obtener(servicio_id)
        if not doc:
            return False, "Servicio no encontrado"
        return True, doc

    @staticmethod
    def actualizar(servicio_id: str, datos: dict):
        doc = ServicioModel.obtener(servicio_id)
        if not doc:
            return False, "Servicio no encontrado"
        ServicioModel.actualizar(servicio_id, datos)
        return True, "Servicio actualizado correctamente"

    @staticmethod
    def cambiar_estado(servicio_id: str, activo: bool):
        ServicioModel.cambiar_estado(servicio_id, activo)
        return True, "Estado actualizado"

    @staticmethod
    def eliminar(servicio_id: str):
        ServicioModel.eliminar(servicio_id)
        return True, "Servicio eliminado"
