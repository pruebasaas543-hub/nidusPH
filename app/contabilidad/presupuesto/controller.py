"""
app/contabilidad/presupuesto/controller.py
────────────────────────────────────────────
Lógica de negocio para presupuesto anual y seguimiento.
"""

from app.contabilidad.presupuesto.model import PresupuestoModel
from app.contabilidad.utils import audit_log


class PresupuestoController:

    @staticmethod
    def obtener(empresa_id: str, anio: int):
        if not empresa_id or not anio:
            return False, "empresa_id y anio son obligatorios"
        pres = PresupuestoModel.obtener(empresa_id, int(anio))
        if not pres:
            return False, f"No existe presupuesto para {anio}"
        pres_id = str(pres["_id"])
        pres["lineas"] = PresupuestoModel.listar_lineas(pres_id)
        return True, pres

    @staticmethod
    def crear(datos: dict, usuario_id: str, ip: str = ""):
        empresa_id = datos.get("empresa_id")
        anio = datos.get("anio")
        if not empresa_id:
            return False, "empresa_id es obligatorio"
        if not anio:
            return False, "anio es obligatorio"
        try:
            anio = int(anio)
        except (ValueError, TypeError):
            return False, "anio debe ser un número entero"

        existente = PresupuestoModel.obtener(empresa_id, anio)
        if existente:
            return False, f"Ya existe un presupuesto para {anio}"

        datos["aprobado_por"] = usuario_id
        pres_id = PresupuestoModel.crear(datos)

        # Crear líneas si vienen en el payload
        lineas = datos.get("lineas", [])
        for linea in lineas:
            if not linea.get("cuenta_id"):
                continue
            if not isinstance(linea.get("valores_mes"), list) or len(linea["valores_mes"]) != 12:
                linea["valores_mes"] = [0.0] * 12
            PresupuestoModel.crear_linea(pres_id, linea)

        audit_log(
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            accion="crear_presupuesto",
            modulo="presupuesto",
            ref_id=pres_id,
            ip=ip,
            datos_antes=None,
            datos_despues={"empresa_id": empresa_id, "anio": anio},
        )
        return True, {"id": pres_id, "mensaje": "Presupuesto creado correctamente"}

    @staticmethod
    def actualizar_linea(presupuesto_id: str, datos: dict, usuario_id: str, ip: str = ""):
        if not presupuesto_id:
            return False, "presupuesto_id requerido"
        linea_id = datos.get("linea_id")
        if not linea_id:
            # Crear nueva línea
            if not datos.get("cuenta_id"):
                return False, "cuenta_id es obligatorio para nueva línea"
            vals = datos.get("valores_mes", [0.0] * 12)
            if len(vals) != 12:
                return False, "valores_mes debe tener 12 valores (uno por mes)"
            nuevo_id = PresupuestoModel.crear_linea(presupuesto_id, datos)
            return True, {"id": nuevo_id, "mensaje": "Línea de presupuesto creada"}
        else:
            pres = PresupuestoModel.obtener_por_id(presupuesto_id)
            if not pres:
                return False, "Presupuesto no encontrado"
            PresupuestoModel.actualizar_linea(linea_id, datos)
            audit_log(
                empresa_id=pres.get("empresa_id", ""),
                usuario_id=usuario_id,
                accion="actualizar_linea_presupuesto",
                modulo="presupuesto",
                ref_id=linea_id,
                ip=ip,
                datos_antes=None,
                datos_despues=datos,
            )
            return True, "Línea de presupuesto actualizada"
