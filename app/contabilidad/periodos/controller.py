"""
app/contabilidad/periodos/controller.py
─────────────────────────────────────────
Lógica de negocio para periodos contables.
"""

from app.contabilidad.periodos.model import PeriodoModel
from app.contabilidad.utils import audit_log


class PeriodoController:

    @staticmethod
    def listar(empresa_id: str):
        if not empresa_id:
            return False, "empresa_id requerido"
        lista = PeriodoModel.listar(empresa_id)
        return True, lista

    @staticmethod
    def crear(datos: dict, usuario_id: str, ip: str = ""):
        empresa_id = datos.get("empresa_id")
        anio = datos.get("anio")
        mes = datos.get("mes")
        if not empresa_id:
            return False, "empresa_id es obligatorio"
        if not anio or not mes:
            return False, "anio y mes son obligatorios"
        try:
            anio = int(anio)
            mes = int(mes)
        except (ValueError, TypeError):
            return False, "anio y mes deben ser números enteros"
        if mes < 1 or mes > 12:
            return False, "El mes debe estar entre 1 y 12"
        existente = PeriodoModel.buscar(empresa_id, anio, mes)
        if existente:
            return False, f"Ya existe un periodo para {anio}-{mes:02d} en esta empresa"

        datos["anio"] = anio
        datos["mes"] = mes
        periodo_id = PeriodoModel.crear(datos)
        audit_log(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            accion="crear_periodo",
            modulo="periodos",
            ref_id=periodo_id,
            ip=ip,
            datos_antes=None,
            datos_despues=datos,
        )
        return True, {"id": periodo_id, "mensaje": "Periodo contable creado correctamente"}

    @staticmethod
    def cerrar(periodo_id: str, usuario_id: str, ip: str = ""):
        if not periodo_id:
            return False, "periodo_id requerido"
        periodo = PeriodoModel.obtener(periodo_id)
        if not periodo:
            return False, "Periodo no encontrado"
        if periodo.get("estado") == "cerrado":
            return False, "El periodo ya está cerrado"
        PeriodoModel.cerrar(periodo_id, usuario_id)
        audit_log(
            empresa_id=periodo.get("empresa_id", ""),
            usuario_id=usuario_id,
            accion="cerrar_periodo",
            modulo="periodos",
            ref_id=periodo_id,
            ip=ip,
            datos_antes={"estado": "abierto"},
            datos_despues={"estado": "cerrado", "cerrado_por": usuario_id},
        )
        return True, "Periodo cerrado correctamente"
