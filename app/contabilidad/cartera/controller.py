"""
app/contabilidad/cartera/controller.py
────────────────────────────────────────
Lógica de negocio para cartera (cuentas por cobrar) y acuerdos de pago.
"""

from datetime import datetime, date
from app.contabilidad.cartera.model import CarteraModel
from app.contabilidad.utils import audit_log

# Tasa de mora diaria por defecto (0.1 % diario)
TASA_MORA_DIARIA = 0.001


class CarteraController:

    @staticmethod
    def listar(empresa_id: str, filtros: dict = None):
        if not empresa_id:
            return False, "empresa_id requerido"
        lista = CarteraModel.listar(empresa_id, filtros)
        return True, lista

    @staticmethod
    def crear(datos: dict, usuario_id: str, ip: str = ""):
        empresa_id = datos.get("empresa_id")
        if not empresa_id:
            return False, "empresa_id es obligatorio"
        if not datos.get("concepto"):
            return False, "El concepto es obligatorio"
        try:
            float(datos.get("valor", 0))
        except (ValueError, TypeError):
            return False, "El valor debe ser numérico"

        cartera_id = CarteraModel.crear(datos)
        audit_log(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            accion="crear_cartera",
            modulo="cartera",
            ref_id=cartera_id,
            ip=ip,
            datos_antes=None,
            datos_despues=datos,
        )
        return True, {"id": cartera_id, "mensaje": "Cuota de cartera registrada"}

    @staticmethod
    def calcular_mora(cartera_id: str, usuario_id: str, ip: str = "", tasa: float = None):
        """Calcula días vencidos × tasa diaria × saldo_pendiente y actualiza el registro."""
        if not cartera_id:
            return False, "cartera_id requerido"
        registro = CarteraModel.obtener(cartera_id)
        if not registro:
            return False, "Registro de cartera no encontrado"
        if registro.get("estado") == "pagada":
            return False, "La cuota ya está pagada, no genera mora"

        fecha_venc_str = registro.get("fecha_vencimiento")
        if not fecha_venc_str:
            return False, "La cuota no tiene fecha de vencimiento"

        try:
            if isinstance(fecha_venc_str, str):
                fecha_venc = datetime.strptime(fecha_venc_str[:10], "%Y-%m-%d").date()
            else:
                fecha_venc = fecha_venc_str
        except Exception:
            return False, "Formato de fecha de vencimiento inválido"

        hoy = date.today()
        dias_vencidos = (hoy - fecha_venc).days
        if dias_vencidos <= 0:
            return False, "La cuota no está vencida aún"

        saldo = float(registro.get("saldo_pendiente", 0))
        tasa_diaria = tasa if tasa is not None else TASA_MORA_DIARIA
        mora = round(dias_vencidos * tasa_diaria * saldo, 2)

        CarteraModel.actualizar_mora(cartera_id, mora)
        audit_log(
            empresa_id=registro.get("empresa_id", ""),
            usuario_id=usuario_id,
            accion="calcular_mora",
            modulo="cartera",
            ref_id=cartera_id,
            ip=ip,
            datos_antes={"mora_acumulada": registro.get("mora_acumulada", 0)},
            datos_despues={"dias_vencidos": dias_vencidos, "mora_acumulada": mora},
        )
        return True, {
            "dias_vencidos": dias_vencidos,
            "tasa_diaria":   tasa_diaria,
            "saldo_pendiente": saldo,
            "mora_calculada":  mora,
        }

    # ── Acuerdos de pago ─────────────────────────────────────────────────────

    @staticmethod
    def crear_acuerdo(datos: dict, usuario_id: str, ip: str = ""):
        empresa_id = datos.get("empresa_id")
        if not empresa_id:
            return False, "empresa_id es obligatorio"
        if not datos.get("cartera_ids"):
            return False, "Debe incluir al menos una cuota de cartera"
        if not datos.get("cuotas"):
            return False, "Debe definir las cuotas del acuerdo"

        acuerdo_id = CarteraModel.crear_acuerdo(datos)
        audit_log(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            accion="crear_acuerdo_pago",
            modulo="cartera",
            ref_id=acuerdo_id,
            ip=ip,
            datos_antes=None,
            datos_despues=datos,
        )
        return True, {"id": acuerdo_id, "mensaje": "Acuerdo de pago creado correctamente"}

    @staticmethod
    def listar_acuerdos(empresa_id: str):
        if not empresa_id:
            return False, "empresa_id requerido"
        lista = CarteraModel.listar_acuerdos(empresa_id)
        return True, lista
