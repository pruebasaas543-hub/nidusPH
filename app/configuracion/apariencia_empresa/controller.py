"""
app/configuracion/apariencia_empresa/controller.py
"""

from app.configuracion.apariencia_empresa.model import AparienciaEmpresaModel
from app.configuracion.apariencias.model import AparienciaModel


class AparienciaEmpresaController:

    @staticmethod
    def listar_por_empresa(empresa_id: str):
        if not empresa_id:
            return False, "ID de empresa requerido"
        return True, AparienciaEmpresaModel.listar_por_empresa(empresa_id)

    @staticmethod
    def asociar_multiples(empresa_id: str, apariencia_ids: list, creado_por: str):
        if not empresa_id:
            return False, "ID de empresa requerido"
        if not apariencia_ids:
            return False, "Debes seleccionar al menos un tema"
        insertados = AparienciaEmpresaModel.asociar_multiples(empresa_id, apariencia_ids, creado_por)
        if insertados == 0:
            return False, "Los temas seleccionados ya están asociados a esta empresa"
        return True, f"{insertados} tema(s) asociado(s) correctamente"

    @staticmethod
    def desasociar_uno(empresa_id: str, apariencia_id: str):
        if not empresa_id or not apariencia_id:
            return False, "IDs requeridos"
        AparienciaEmpresaModel.desasociar_uno(empresa_id, apariencia_id)
        return True, "Tema quitado correctamente"

    @staticmethod
    def crear_y_asociar(empresa_id: str, datos: dict, creado_por: str):
        if not empresa_id:
            return False, "ID de empresa requerido"
        nombre = (datos.get("nombre") or "").strip()
        clave  = (datos.get("clave")  or "").strip()
        if not nombre:
            return False, "El nombre del tema es requerido"
        if not clave:
            return False, "La clave del tema es requerida"
        if AparienciaModel.buscar_por_clave(clave):
            return False, f"Ya existe un tema con la clave '{clave}'"
        apariencia_id = AparienciaModel.crear(datos)
        AparienciaEmpresaModel.asociar_multiples(empresa_id, [apariencia_id], creado_por)
        return True, {"apariencia_id": apariencia_id, "mensaje": "Tema creado y asociado correctamente"}

    @staticmethod
    def listar():
        return True, AparienciaEmpresaModel.listar_con_detalle()
