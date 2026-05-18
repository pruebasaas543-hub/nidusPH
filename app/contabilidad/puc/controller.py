"""
app/contabilidad/puc/controller.py
───────────────────────────────────
Lógica de negocio para el Plan Único de Cuentas.
"""

from app.contabilidad.puc.model import PucModel
from app.contabilidad.utils import audit_log

# ── Plantillas PUC para Propiedad Horizontal ──────────────────────────────────
# Estructura mínima y representativa. Se puede ampliar por cada perfil.

_PLANTILLA_BASE = [
    # CLASE 1 — ACTIVO
    {"codigo": "1",    "nombre": "ACTIVO",                         "naturaleza": "D", "nivel": 1},
    {"codigo": "11",   "nombre": "EFECTIVO Y EQUIVALENTES",        "naturaleza": "D", "nivel": 2},
    {"codigo": "1105", "nombre": "Caja",                           "naturaleza": "D", "nivel": 3, "exige_tercero": False},
    {"codigo": "1110", "nombre": "Bancos",                         "naturaleza": "D", "nivel": 3, "exige_tercero": True},
    {"codigo": "1115", "nombre": "Fondos",                         "naturaleza": "D", "nivel": 3},
    {"codigo": "13",   "nombre": "DEUDORES",                       "naturaleza": "D", "nivel": 2},
    {"codigo": "1305", "nombre": "Clientes - Cuotas Administración","naturaleza": "D", "nivel": 3, "exige_tercero": True},
    {"codigo": "1310", "nombre": "Anticipos a Proveedores",        "naturaleza": "D", "nivel": 3, "exige_tercero": True},
    {"codigo": "1330", "nombre": "Deudores Varios",                "naturaleza": "D", "nivel": 3, "exige_tercero": True},
    {"codigo": "15",   "nombre": "PROPIEDADES PLANTA Y EQUIPO",    "naturaleza": "D", "nivel": 2},
    {"codigo": "1504", "nombre": "Equipos de Oficina",             "naturaleza": "D", "nivel": 3, "exige_centro_costos": True},
    {"codigo": "1516", "nombre": "Maquinaria y Equipo",            "naturaleza": "D", "nivel": 3, "exige_centro_costos": True},
    {"codigo": "1592", "nombre": "Depreciación Acumulada",         "naturaleza": "C", "nivel": 3},
    # CLASE 2 — PASIVO
    {"codigo": "2",    "nombre": "PASIVO",                         "naturaleza": "C", "nivel": 1},
    {"codigo": "22",   "nombre": "PROVEEDORES",                    "naturaleza": "C", "nivel": 2},
    {"codigo": "2205", "nombre": "Proveedores Nacionales",         "naturaleza": "C", "nivel": 3, "exige_tercero": True},
    {"codigo": "23",   "nombre": "CUENTAS POR PAGAR",              "naturaleza": "C", "nivel": 2},
    {"codigo": "2335", "nombre": "Costas y Gastos por Pagar",      "naturaleza": "C", "nivel": 3},
    {"codigo": "2380", "nombre": "Acreedores Varios",              "naturaleza": "C", "nivel": 3, "exige_tercero": True},
    {"codigo": "24",   "nombre": "IMPUESTOS GRAVÁMENES Y TASAS",   "naturaleza": "C", "nivel": 2},
    {"codigo": "2404", "nombre": "De Renta y Complementarios",     "naturaleza": "C", "nivel": 3},
    {"codigo": "2408", "nombre": "IVA por Pagar",                  "naturaleza": "C", "nivel": 3},
    {"codigo": "2365", "nombre": "Retención en la Fuente por Pagar","naturaleza": "C", "nivel": 3, "exige_tercero": True},
    {"codigo": "25",   "nombre": "OBLIGACIONES LABORALES",         "naturaleza": "C", "nivel": 2},
    {"codigo": "2505", "nombre": "Salarios por Pagar",             "naturaleza": "C", "nivel": 3},
    {"codigo": "2510", "nombre": "Cesantías Consolidadas",         "naturaleza": "C", "nivel": 3},
    # CLASE 3 — PATRIMONIO
    {"codigo": "3",    "nombre": "PATRIMONIO",                     "naturaleza": "C", "nivel": 1},
    {"codigo": "32",   "nombre": "SUPERÁVIT DE CAPITAL",           "naturaleza": "C", "nivel": 2},
    {"codigo": "3205", "nombre": "Fondo de Reserva",               "naturaleza": "C", "nivel": 3},
    {"codigo": "36",   "nombre": "RESULTADOS DEL EJERCICIO",       "naturaleza": "C", "nivel": 2},
    {"codigo": "3605", "nombre": "Utilidad del Ejercicio",         "naturaleza": "C", "nivel": 3},
    {"codigo": "3610", "nombre": "Pérdida del Ejercicio",          "naturaleza": "D", "nivel": 3},
    # CLASE 4 — INGRESOS
    {"codigo": "4",    "nombre": "INGRESOS",                       "naturaleza": "C", "nivel": 1},
    {"codigo": "41",   "nombre": "OPERACIONALES",                  "naturaleza": "C", "nivel": 2},
    {"codigo": "4105", "nombre": "Cuotas de Administración",       "naturaleza": "C", "nivel": 3, "exige_centro_costos": True},
    {"codigo": "4110", "nombre": "Cuotas Extraordinarias",         "naturaleza": "C", "nivel": 3},
    {"codigo": "4135", "nombre": "Intereses de Mora",              "naturaleza": "C", "nivel": 3, "exige_tercero": True},
    {"codigo": "42",   "nombre": "NO OPERACIONALES",               "naturaleza": "C", "nivel": 2},
    {"codigo": "4210", "nombre": "Arrendamientos - Zonas Comunes", "naturaleza": "C", "nivel": 3, "exige_tercero": True},
    {"codigo": "4250", "nombre": "Recuperaciones",                 "naturaleza": "C", "nivel": 3},
    # CLASE 5 — GASTOS
    {"codigo": "5",    "nombre": "GASTOS",                         "naturaleza": "D", "nivel": 1},
    {"codigo": "51",   "nombre": "OPERACIONALES DE ADMINISTRACIÓN","naturaleza": "D", "nivel": 2},
    {"codigo": "5105", "nombre": "Gastos de Personal",             "naturaleza": "D", "nivel": 3, "exige_centro_costos": True},
    {"codigo": "5110", "nombre": "Honorarios",                     "naturaleza": "D", "nivel": 3, "exige_tercero": True},
    {"codigo": "5115", "nombre": "Arrendamientos",                 "naturaleza": "D", "nivel": 3, "exige_tercero": True},
    {"codigo": "5120", "nombre": "Seguros",                        "naturaleza": "D", "nivel": 3, "exige_tercero": True},
    {"codigo": "5125", "nombre": "Servicios Públicos",             "naturaleza": "D", "nivel": 3, "exige_tercero": True},
    {"codigo": "5130", "nombre": "Mantenimiento y Reparaciones",   "naturaleza": "D", "nivel": 3, "exige_tercero": True, "exige_centro_costos": True},
    {"codigo": "5135", "nombre": "Vigilancia y Seguridad",         "naturaleza": "D", "nivel": 3, "exige_tercero": True},
    {"codigo": "5140", "nombre": "Aseo y Limpieza",                "naturaleza": "D", "nivel": 3, "exige_tercero": True},
    {"codigo": "5145", "nombre": "Correo y Telecomunicaciones",    "naturaleza": "D", "nivel": 3},
    {"codigo": "5195", "nombre": "Gastos Diversos",                "naturaleza": "D", "nivel": 3},
    {"codigo": "52",   "nombre": "NO OPERACIONALES",               "naturaleza": "D", "nivel": 2},
    {"codigo": "5205", "nombre": "Gastos Financieros",             "naturaleza": "D", "nivel": 3},
    {"codigo": "5250", "nombre": "Multas y Sanciones",             "naturaleza": "D", "nivel": 3},
    # CLASE 6 — COSTOS (si aplica en PH Comercial/Mixto)
    {"codigo": "6",    "nombre": "COSTOS DE VENTAS",               "naturaleza": "D", "nivel": 1},
    {"codigo": "61",   "nombre": "COSTOS OPERACIONALES",           "naturaleza": "D", "nivel": 2},
    {"codigo": "6135", "nombre": "Depreciaciones",                 "naturaleza": "D", "nivel": 3},
]

_PLANTILLAS = {
    "residencial": _PLANTILLA_BASE,
    "comercial":   _PLANTILLA_BASE,  # Se puede diferenciar en versión futura
    "mixto":       _PLANTILLA_BASE,
}


class PucController:

    @staticmethod
    def listar(filtros: dict = None):
        lista = PucModel.listar(filtros)
        return True, lista

    @staticmethod
    def listar_arbol(filtros: dict = None):
        """Devuelve el PUC como árbol jerárquico ordenado por código."""
        cuentas = PucModel.listar(filtros)
        # Convertir _id a string para serialización
        for c in cuentas:
            c["_id"] = str(c["_id"])
        # Construir árbol
        por_id = {c["_id"]: {**c, "hijos": []} for c in cuentas}
        raices = []
        for c in por_id.values():
            padre_id = str(c.get("padre_id") or "")
            if padre_id and padre_id in por_id:
                por_id[padre_id]["hijos"].append(c)
            else:
                raices.append(c)
        return True, raices

    @staticmethod
    def crear(datos: dict, usuario_id: str, ip: str = ""):
        if not datos.get("codigo"):
            return False, "El código de cuenta es obligatorio"
        if not datos.get("nombre"):
            return False, "El nombre de cuenta es obligatorio"
        if datos.get("naturaleza") not in ("D", "C", None):
            return False, "La naturaleza debe ser D (Débito) o C (Crédito)"
        if PucModel.buscar_por_codigo(datos["codigo"]):
            return False, f"Ya existe una cuenta con el código {datos['codigo']}"

        cuenta_id = PucModel.crear(datos)
        audit_log(
            empresa_id=datos.get("empresa_id", "global"),
            usuario_id=usuario_id,
            accion="crear_cuenta_puc",
            modulo="puc",
            ref_id=cuenta_id,
            ip=ip,
            datos_antes=None,
            datos_despues={k: v for k, v in datos.items()},
        )
        return True, {"id": cuenta_id, "mensaje": "Cuenta PUC creada correctamente"}

    @staticmethod
    def actualizar(cuenta_id: str, datos: dict, usuario_id: str, ip: str = ""):
        if not cuenta_id:
            return False, "ID de cuenta requerido"
        anterior = PucModel.obtener(cuenta_id)
        if not anterior:
            return False, "Cuenta no encontrada"
        # RN-PUC-01: bloquear cambio de código
        if "codigo" in datos and str(datos["codigo"]).strip() != str(anterior.get("codigo", "")):
            return False, "RN-PUC-01: El código de cuenta no puede modificarse. Cree una cuenta nueva."
        datos.pop("codigo", None)
        PucModel.actualizar(cuenta_id, datos)
        audit_log(
            empresa_id=datos.get("empresa_id", "global"),
            usuario_id=usuario_id,
            accion="actualizar_cuenta_puc",
            modulo="puc",
            ref_id=cuenta_id,
            ip=ip,
            datos_antes={k: str(v) for k, v in anterior.items()},
            datos_despues=datos,
        )
        return True, "Cuenta PUC actualizada correctamente"

    @staticmethod
    def cambiar_estado(cuenta_id: str, activa: bool, usuario_id: str, ip: str = ""):
        """RN-PUC-03: Inactivación suave para cuentas con movimientos."""
        if not cuenta_id:
            return False, "ID de cuenta requerido"
        cuenta = PucModel.obtener(cuenta_id)
        if not cuenta:
            return False, "Cuenta no encontrada"
        PucModel.cambiar_estado(cuenta_id, activa)
        audit_log(
            empresa_id="global",
            usuario_id=usuario_id,
            accion="inactivar_cuenta_puc" if not activa else "activar_cuenta_puc",
            modulo="puc",
            ref_id=cuenta_id,
            ip=ip,
            datos_antes={"activa": cuenta.get("activa")},
            datos_despues={"activa": activa},
        )
        accion_txt = "activada" if activa else "inactivada"
        return True, f"Cuenta {accion_txt} correctamente"

    @staticmethod
    def eliminar(cuenta_id: str, usuario_id: str, ip: str = ""):
        if not cuenta_id:
            return False, "ID de cuenta requerido"
        cuenta = PucModel.obtener(cuenta_id)
        if not cuenta:
            return False, "Cuenta no encontrada"
        # RN-PUC-02: protección por asientos O saldo inicial
        if PucModel.tiene_movimientos(cuenta_id):
            return False, (
                "RN-PUC-02: No se puede eliminar. La cuenta tiene movimientos o saldo inicial registrado. "
                "Use la opción Inactivar."
            )
        PucModel.eliminar(cuenta_id)
        audit_log(
            empresa_id="global",
            usuario_id=usuario_id,
            accion="eliminar_cuenta_puc",
            modulo="puc",
            ref_id=cuenta_id,
            ip=ip,
            datos_antes={k: str(v) for k, v in cuenta.items()},
            datos_despues=None,
        )
        return True, "Cuenta PUC eliminada correctamente"

    @staticmethod
    def cargar_plantilla(perfil: str, usuario_id: str, ip: str = ""):
        """Carga una plantilla predeterminada de PUC para el perfil dado."""
        perfil = (perfil or "residencial").lower()
        cuentas = _PLANTILLAS.get(perfil)
        if not cuentas:
            return False, f"Perfil '{perfil}' no encontrado. Opciones: residencial, comercial, mixto"
        resultado = PucModel.importar_lote(cuentas)
        audit_log(
            empresa_id="global",
            usuario_id=usuario_id,
            accion=f"cargar_plantilla_puc_{perfil}",
            modulo="puc",
            ref_id=None,
            ip=ip,
            datos_antes=None,
            datos_despues=resultado,
        )
        return True, resultado

    @staticmethod
    def importar(cuentas: list, usuario_id: str, ip: str = ""):
        """Importación masiva desde Excel/CSV ya parseado."""
        if not isinstance(cuentas, list) or not cuentas:
            return False, "Se requiere una lista de cuentas"
        resultado = PucModel.importar_lote(cuentas)
        audit_log(
            empresa_id="global",
            usuario_id=usuario_id,
            accion="importar_puc_masivo",
            modulo="puc",
            ref_id=None,
            ip=ip,
            datos_antes=None,
            datos_despues=resultado,
        )
        return True, resultado

    @staticmethod
    def cuentas_niif():
        return True, PucModel.cuentas_niif()
