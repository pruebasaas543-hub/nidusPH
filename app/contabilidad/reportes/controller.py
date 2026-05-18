"""
app/contabilidad/reportes/controller.py
─────────────────────────────────────────
Lógica de negocio para reportes financieros.
"""

from app.contabilidad.reportes.model import ReportesModel
from app import db


class ReportesController:

    @staticmethod
    def balance_general(empresa_id: str):
        """
        Genera el balance general clasificando cuentas por nivel.
        Activos (naturaleza D, clase 1), Pasivos (C, clase 2), Patrimonio (C, clase 3).
        """
        if not empresa_id:
            return False, "empresa_id requerido"

        saldos = ReportesModel.saldos_asentados_por_cuenta(empresa_id)

        # Enriquecer con datos del PUC
        activos = []
        pasivos = []
        patrimonio = []
        total_activos = 0.0
        total_pasivos = 0.0
        total_patrimonio = 0.0

        for item in saldos:
            cuenta_id = item["_id"]
            cuenta = db["cont_puc"].find_one({"codigo": cuenta_id}) or \
                     db["cont_puc"].find_one({"_id": __import__("bson").ObjectId(cuenta_id)
                                              if len(str(cuenta_id)) == 24 else None}) \
                     if len(str(cuenta_id)) == 24 else db["cont_puc"].find_one({"codigo": cuenta_id})
            if not cuenta:
                cuenta = {"codigo": cuenta_id, "nombre": cuenta_id, "naturaleza": "D", "nivel": 1}

            saldo = item["saldo"]
            entrada = {
                "cuenta_id":  cuenta_id,
                "codigo":     cuenta.get("codigo", cuenta_id),
                "nombre":     cuenta.get("nombre", cuenta_id),
                "debitos":    round(item["debitos"], 2),
                "creditos":   round(item["creditos"], 2),
                "saldo":      round(abs(saldo), 2),
            }
            codigo = str(cuenta.get("codigo", ""))
            if codigo.startswith("1"):
                activos.append(entrada)
                total_activos += abs(saldo)
            elif codigo.startswith("2"):
                pasivos.append(entrada)
                total_pasivos += abs(saldo)
            elif codigo.startswith("3"):
                patrimonio.append(entrada)
                total_patrimonio += abs(saldo)

        return True, {
            "activos":         activos,
            "pasivos":         pasivos,
            "patrimonio":      patrimonio,
            "total_activos":   round(total_activos, 2),
            "total_pasivos":   round(total_pasivos, 2),
            "total_patrimonio": round(total_patrimonio, 2),
            "cuadra":          abs(total_activos - (total_pasivos + total_patrimonio)) < 0.01,
        }

    @staticmethod
    def estado_resultados(empresa_id: str):
        """
        Estado de resultados: ingresos (clase 4) vs costos/gastos (clase 5/6).
        """
        if not empresa_id:
            return False, "empresa_id requerido"

        saldos = ReportesModel.saldos_asentados_por_cuenta(empresa_id)
        ingresos = []
        costos_gastos = []
        total_ingresos = 0.0
        total_costos = 0.0

        for item in saldos:
            cuenta_id = item["_id"]
            cuenta = db["cont_puc"].find_one({"codigo": cuenta_id})
            if not cuenta:
                cuenta = {"codigo": cuenta_id, "nombre": cuenta_id}

            saldo = item["saldo"]
            codigo = str(cuenta.get("codigo", ""))
            entrada = {
                "cuenta_id": cuenta_id,
                "codigo":    cuenta.get("codigo", cuenta_id),
                "nombre":    cuenta.get("nombre", cuenta_id),
                "valor":     round(abs(saldo), 2),
            }

            if codigo.startswith("4"):
                ingresos.append(entrada)
                total_ingresos += abs(saldo)
            elif codigo.startswith("5") or codigo.startswith("6"):
                costos_gastos.append(entrada)
                total_costos += abs(saldo)

        utilidad = round(total_ingresos - total_costos, 2)
        return True, {
            "ingresos":       ingresos,
            "costos_gastos":  costos_gastos,
            "total_ingresos": round(total_ingresos, 2),
            "total_costos":   round(total_costos, 2),
            "utilidad_neta":  utilidad,
        }

    @staticmethod
    def auxiliar_cuenta(empresa_id: str, cuenta_id: str):
        if not empresa_id or not cuenta_id:
            return False, "empresa_id y cuenta_id son obligatorios"
        movimientos = ReportesModel.auxiliar_cuenta(empresa_id, cuenta_id)
        saldo_acum = 0.0
        for m in movimientos:
            saldo_acum += m.get("debito", 0) - m.get("credito", 0)
            m["saldo_acumulado"] = round(saldo_acum, 2)
        return True, movimientos

    @staticmethod
    def dashboard(empresa_id: str):
        if not empresa_id:
            return False, "empresa_id requerido"
        kpis = ReportesModel.kpis_dashboard(empresa_id)
        return True, kpis
