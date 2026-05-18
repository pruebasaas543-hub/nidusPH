"""
app/contabilidad/comprobantes/controller.py
─────────────────────────────────────────────
Lógica de negocio para comprobantes de diario y asientos.
Valida: periodo abierto, partida doble, audit log.
"""

from app.contabilidad.comprobantes.model import ComprobantesModel
from app.contabilidad.utils import audit_log, verificar_periodo_abierto


class ComprobantesController:

    @staticmethod
    def listar(empresa_id: str, filtros: dict = None):
        if not empresa_id:
            return False, "empresa_id requerido"
        lista = ComprobantesModel.listar(empresa_id, filtros)
        return True, lista

    @staticmethod
    def crear(datos: dict, usuario_id: str, ip: str = ""):
        empresa_id = datos.get("empresa_id")
        if not empresa_id:
            return False, "empresa_id es obligatorio"
        if not datos.get("concepto"):
            return False, "El concepto es obligatorio"

        # Verificar periodo abierto
        anio = datos.get("anio")
        mes = datos.get("mes")
        if anio and mes:
            ok_periodo, periodo_info = verificar_periodo_abierto(empresa_id, int(anio), int(mes))
            if not ok_periodo:
                return False, periodo_info
            datos["periodo_id"] = periodo_info

        datos["creado_por"] = usuario_id
        comp_id = ComprobantesModel.crear(datos)

        # Crear asientos si vienen en el payload
        asientos = datos.get("asientos", [])
        for linea in asientos:
            linea["empresa_id"] = empresa_id
            ComprobantesModel.crear_asiento(comp_id, linea)

        audit_log(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            accion="crear_comprobante",
            modulo="comprobantes",
            ref_id=comp_id,
            ip=ip,
            datos_antes=None,
            datos_despues={k: v for k, v in datos.items() if k != "asientos"},
        )
        return True, {"id": comp_id, "mensaje": "Comprobante creado en estado borrador"}

    @staticmethod
    def asentar(comprobante_id: str, usuario_id: str, ip: str = ""):
        """Asienta el comprobante validando partida doble y periodo abierto."""
        if not comprobante_id:
            return False, "comprobante_id requerido"

        comp = ComprobantesModel.obtener(comprobante_id)
        if not comp:
            return False, "Comprobante no encontrado"
        if comp.get("estado") == "asentado":
            return False, "El comprobante ya está asentado"

        # Verificar periodo abierto
        if comp.get("periodo_id"):
            from app import db
            from bson import ObjectId
            periodo = db["cont_periodos"].find_one({"_id": ObjectId(comp["periodo_id"])})
            if periodo and periodo.get("estado") != "abierto":
                return False, "No se puede asentar: el periodo contable está cerrado"

        # Partida doble
        total_d, total_c = ComprobantesModel.sumar_debitos_creditos(comprobante_id)
        if total_d == 0 and total_c == 0:
            return False, "El comprobante no tiene asientos registrados"
        if abs(total_d - total_c) > 0.01:
            return False, (
                f"Partida doble no cuadra: débitos={total_d:.2f}, créditos={total_c:.2f}"
            )

        ComprobantesModel.asentar(comprobante_id)
        audit_log(
            empresa_id=comp.get("empresa_id", ""),
            usuario_id=usuario_id,
            accion="asentar_comprobante",
            modulo="comprobantes",
            ref_id=comprobante_id,
            ip=ip,
            datos_antes={"estado": "borrador"},
            datos_despues={"estado": "asentado", "total_debitos": total_d, "total_creditos": total_c},
        )
        return True, {"mensaje": "Comprobante asentado correctamente", "total_debitos": total_d}

    @staticmethod
    def obtener_con_asientos(comprobante_id: str):
        if not comprobante_id:
            return False, "comprobante_id requerido"
        comp = ComprobantesModel.obtener(comprobante_id)
        if not comp:
            return False, "Comprobante no encontrado"
        comp["asientos"] = ComprobantesModel.obtener_asientos(comprobante_id)
        return True, comp
