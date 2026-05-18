"""
app/contabilidad/activos/controller.py
────────────────────────────────────────
Lógica de negocio para activos fijos y depreciación.
"""

from app.contabilidad.activos.model import ActivosModel
from app.contabilidad.utils import audit_log


class ActivosController:

    @staticmethod
    def listar(empresa_id: str):
        if not empresa_id:
            return False, "empresa_id requerido"
        return True, ActivosModel.listar(empresa_id)

    @staticmethod
    def crear(datos: dict, usuario_id: str, ip: str = ""):
        empresa_id = datos.get("empresa_id")
        if not empresa_id:
            return False, "empresa_id es obligatorio"
        if not datos.get("nombre"):
            return False, "El nombre del activo es obligatorio"
        try:
            valor_hist = float(datos.get("valor_historico", 0))
            vida_util  = int(datos.get("vida_util_meses", 1))
        except (ValueError, TypeError):
            return False, "valor_historico y vida_util_meses deben ser numéricos"
        if valor_hist <= 0:
            return False, "El valor histórico debe ser mayor a 0"
        if vida_util <= 0:
            return False, "La vida útil debe ser mayor a 0 meses"

        activo_id = ActivosModel.crear(datos)
        audit_log(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            accion="crear_activo",
            modulo="activos",
            ref_id=activo_id,
            ip=ip,
            datos_antes=None,
            datos_despues=datos,
        )
        return True, {"id": activo_id, "mensaje": "Activo fijo creado correctamente"}

    @staticmethod
    def actualizar(activo_id: str, datos: dict, usuario_id: str, ip: str = ""):
        if not activo_id:
            return False, "activo_id requerido"
        anterior = ActivosModel.obtener(activo_id)
        if not anterior:
            return False, "Activo no encontrado"
        ActivosModel.actualizar(activo_id, datos)
        audit_log(
            empresa_id=anterior.get("empresa_id", ""),
            usuario_id=usuario_id,
            accion="actualizar_activo",
            modulo="activos",
            ref_id=activo_id,
            ip=ip,
            datos_antes=anterior,
            datos_despues=datos,
        )
        return True, "Activo actualizado correctamente"

    @staticmethod
    def batch_depreciacion(empresa_id: str, usuario_id: str, ip: str = ""):
        """
        Calcula y registra la depreciación mensual por línea recta para todos
        los activos activos de la empresa. Genera un comprobante de diario automático.
        """
        if not empresa_id:
            return False, "empresa_id requerido"

        activos = ActivosModel.listar_activos_activos(empresa_id)
        if not activos:
            return False, "No hay activos activos con saldo por depreciar"

        resultados = []
        total_depreciacion = 0.0

        for activo in activos:
            activo_id = str(activo["_id"])
            valor_hist = float(activo.get("valor_historico", 0))
            vida_util  = int(activo.get("vida_util_meses", 1))
            dep_acum   = float(activo.get("depreciacion_acumulada", 0))

            dep_mensual = round(valor_hist / vida_util, 2)
            valor_residual = round(valor_hist - dep_acum, 2)

            # No depreciar más allá del valor residual
            if valor_residual <= 0:
                continue
            dep_a_aplicar = min(dep_mensual, valor_residual)

            ActivosModel.acumular_depreciacion(activo_id, dep_a_aplicar)
            total_depreciacion += dep_a_aplicar
            resultados.append({
                "activo_id":     activo_id,
                "nombre":        activo.get("nombre"),
                "depreciacion":  dep_a_aplicar,
            })

        # Generar comprobante de diario automático
        if total_depreciacion > 0:
            from app.contabilidad.comprobantes.model import ComprobantesModel
            from datetime import datetime
            comp_datos = {
                "empresa_id":    empresa_id,
                "tipo":          "auto",
                "concepto":      f"Depreciación mensual activos fijos – {datetime.utcnow().strftime('%Y-%m')}",
                "origen_modulo": "activos",
                "creado_por":    usuario_id,
            }
            comp_id = ComprobantesModel.crear(comp_datos)

        audit_log(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            accion="batch_depreciacion",
            modulo="activos",
            ref_id=None,
            ip=ip,
            datos_antes=None,
            datos_despues={"total_activos": len(resultados), "total_depreciacion": total_depreciacion},
        )
        return True, {
            "total_activos_depreciados": len(resultados),
            "total_depreciacion":        round(total_depreciacion, 2),
            "detalle":                   resultados,
        }
