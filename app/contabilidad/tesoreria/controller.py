"""
app/contabilidad/tesoreria/controller.py
──────────────────────────────────────────
Lógica de negocio para tesorería (cuentas por pagar).
"""

from app.contabilidad.tesoreria.model import TesoreriaModel
from app.contabilidad.utils import audit_log


class TesoreriaController:

    # ── Facturas proveedor ────────────────────────────────────────────────────

    @staticmethod
    def listar_facturas(empresa_id: str):
        if not empresa_id:
            return False, "empresa_id requerido"
        return True, TesoreriaModel.listar_facturas(empresa_id)

    @staticmethod
    def radicar_factura(datos: dict, usuario_id: str, ip: str = ""):
        empresa_id = datos.get("empresa_id")
        if not empresa_id:
            return False, "empresa_id es obligatorio"
        if not datos.get("proveedor_nit"):
            return False, "El NIT del proveedor es obligatorio"
        if not datos.get("numero"):
            return False, "El número de factura es obligatorio"
        try:
            subtotal    = float(datos.get("subtotal", 0))
            impuestos   = float(datos.get("impuestos", 0))
            retenciones = float(datos.get("retenciones", 0))
        except (ValueError, TypeError):
            return False, "Los valores monetarios deben ser numéricos"

        datos["total"] = round(subtotal + impuestos - retenciones, 2)
        factura_id = TesoreriaModel.crear_factura(datos)
        audit_log(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            accion="radicar_factura",
            modulo="tesoreria",
            ref_id=factura_id,
            ip=ip,
            datos_antes=None,
            datos_despues=datos,
        )
        return True, {"id": factura_id, "mensaje": "Factura radicada correctamente"}

    @staticmethod
    def aprobar_factura(factura_id: str, usuario_id: str, ip: str = ""):
        if not factura_id:
            return False, "factura_id requerido"
        factura = TesoreriaModel.obtener_factura(factura_id)
        if not factura:
            return False, "Factura no encontrada"
        if factura.get("estado") != "pendiente":
            return False, f"La factura no puede aprobarse (estado actual: {factura.get('estado')})"

        TesoreriaModel.cambiar_estado_factura(factura_id, "aprobada")
        TesoreriaModel.crear_aprobacion(factura_id, usuario_id, "aprobada")
        audit_log(
            empresa_id=factura.get("empresa_id", ""),
            usuario_id=usuario_id,
            accion="aprobar_factura",
            modulo="tesoreria",
            ref_id=factura_id,
            ip=ip,
            datos_antes={"estado": "pendiente"},
            datos_despues={"estado": "aprobada"},
        )
        return True, "Factura aprobada correctamente"

    @staticmethod
    def registrar_pago(factura_id: str, usuario_id: str, ip: str = ""):
        if not factura_id:
            return False, "factura_id requerido"
        factura = TesoreriaModel.obtener_factura(factura_id)
        if not factura:
            return False, "Factura no encontrada"
        if factura.get("estado") != "aprobada":
            return False, "Solo se pueden pagar facturas aprobadas"

        TesoreriaModel.cambiar_estado_factura(factura_id, "pagada")
        audit_log(
            empresa_id=factura.get("empresa_id", ""),
            usuario_id=usuario_id,
            accion="pagar_factura",
            modulo="tesoreria",
            ref_id=factura_id,
            ip=ip,
            datos_antes={"estado": "aprobada"},
            datos_despues={"estado": "pagada"},
        )
        return True, "Pago registrado correctamente"

    # ── Programación de pagos ─────────────────────────────────────────────────

    @staticmethod
    def listar_programacion(empresa_id: str):
        if not empresa_id:
            return False, "empresa_id requerido"
        return True, TesoreriaModel.listar_programacion(empresa_id)

    @staticmethod
    def programar_pago(datos: dict, usuario_id: str, ip: str = ""):
        if not datos.get("factura_id"):
            return False, "factura_id es obligatorio"
        if not datos.get("fecha_pago"):
            return False, "La fecha de pago es obligatoria"
        try:
            float(datos.get("valor", 0))
        except (ValueError, TypeError):
            return False, "El valor debe ser numérico"

        pago_id = TesoreriaModel.programar_pago(datos)
        audit_log(
            empresa_id=datos.get("empresa_id", ""),
            usuario_id=usuario_id,
            accion="programar_pago",
            modulo="tesoreria",
            ref_id=pago_id,
            ip=ip,
            datos_antes=None,
            datos_despues=datos,
        )
        return True, {"id": pago_id, "mensaje": "Pago programado correctamente"}
