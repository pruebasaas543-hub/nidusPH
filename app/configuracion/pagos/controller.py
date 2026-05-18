"""
app/configuracion/pagos/controller.py
"""

from app.configuracion.pagos.model import AsociacionDatosPagoModel
from app.configuracion.empresas.model import EmpresaModel


class AsociacionDatosPagoController:

    TIPOS_VALIDOS = ["cuentas_bancarias", "convenios", "billeteras", "corresponsales", "pasarela"]

    @staticmethod
    def crear(empresa_id: str, tipo: str, datos: dict, creado_por: str):
        if not empresa_id:
            return False, "ID de empresa requerido"
        if tipo not in AsociacionDatosPagoController.TIPOS_VALIDOS:
            return False, f"Tipo no válido. Permitidos: {AsociacionDatosPagoController.TIPOS_VALIDOS}"
        doc_id = AsociacionDatosPagoModel.crear(empresa_id, tipo, datos, creado_por)
        return True, {"id": doc_id, "mensaje": f"Configuración de {tipo} registrada"}

    @staticmethod
    def actualizar(config_id: str, datos: dict):
        if not config_id:
            return False, "ID de configuración requerido"
        AsociacionDatosPagoModel.actualizar(config_id, datos)
        return True, "Configuración actualizada correctamente"

    @staticmethod
    def obtener(config_id: str):
        doc = AsociacionDatosPagoModel.obtener(config_id)
        if not doc:
            return False, "Configuración no encontrada"
        return True, doc

    @staticmethod
    def listar_por_empresa(empresa_id: str):
        if not empresa_id:
            return False, "ID de empresa requerido"
        lista = AsociacionDatosPagoModel.listar_por_empresa(empresa_id)
        emp = EmpresaModel.buscar_por_id(empresa_id)
        for cfg in lista:
            cfg["empresa_nombre"] = emp.get("razon_social", "—") if emp else "—"
        return True, lista

    @staticmethod
    def listar_por_tipo(empresa_id: str, tipo: str):
        if not empresa_id:
            return False, "ID de empresa requerido"
        return True, AsociacionDatosPagoModel.listar_por_tipo(empresa_id, tipo)

    @staticmethod
    def eliminar(config_id: str):
        if not config_id:
            return False, "ID de configuración requerido"
        AsociacionDatosPagoModel.eliminar(config_id)
        return True, "Configuración eliminada correctamente"
