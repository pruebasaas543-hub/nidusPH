"""
app/configuracion/apariencias/controller.py
"""

from app.configuracion.apariencias.model import AparienciaModel


class AparienciaController:

    @staticmethod
    def listar():
        AparienciaModel.sembrar_predeterminados()
        temas = AparienciaModel.listar(solo_activos=False)
        return True, temas

    @staticmethod
    def obtener(apariencia_id: str):
        if not apariencia_id:
            return False, "ID requerido"
        doc = AparienciaModel.obtener(apariencia_id)
        if not doc:
            return False, "Apariencia no encontrada"
        return True, doc

    @staticmethod
    def crear(datos: dict):
        nombre = (datos.get("nombre") or "").strip()
        clave  = (datos.get("clave")  or "").strip()
        if not nombre:
            return False, "El nombre es requerido"
        if not clave:
            return False, "La clave es requerida"
        if AparienciaModel.buscar_por_clave(clave):
            return False, f"Ya existe una apariencia con la clave '{clave}'"
        doc_id = AparienciaModel.crear(datos)
        return True, {"id": doc_id, "mensaje": "Apariencia creada correctamente"}

    @staticmethod
    def actualizar(apariencia_id: str, datos: dict):
        if not apariencia_id:
            return False, "ID requerido"
        if not AparienciaModel.obtener(apariencia_id):
            return False, "Apariencia no encontrada"
        AparienciaModel.actualizar(apariencia_id, datos)
        return True, "Apariencia actualizada correctamente"

    @staticmethod
    def eliminar(apariencia_id: str):
        if not apariencia_id:
            return False, "ID requerido"
        doc = AparienciaModel.obtener(apariencia_id)
        if not doc:
            return False, "Apariencia no encontrada"
        if doc.get("es_predeterminado"):
            return False, "No se puede eliminar una apariencia predeterminada del sistema"
        AparienciaModel.eliminar(apariencia_id)
        return True, "Apariencia eliminada correctamente"
