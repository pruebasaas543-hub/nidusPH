"""
app/contabilidad/reportes/model.py
────────────────────────────────────
Consultas MongoDB para generación de reportes financieros.
"""

from app import db
from bson import ObjectId


class ReportesModel:

    @staticmethod
    def saldos_por_cuenta(empresa_id: str) -> list:
        """Agrupa asientos por cuenta y calcula saldo (debito - credito)."""
        pipeline = [
            {"$match": {"empresa_id": empresa_id}},
            {"$group": {
                "_id":     "$cuenta_id",
                "debitos":  {"$sum": "$debito"},
                "creditos": {"$sum": "$credito"},
            }},
            {"$addFields": {
                "saldo": {"$subtract": ["$debitos", "$creditos"]}
            }},
        ]
        return list(db["cont_asientos"].aggregate(pipeline))

    @staticmethod
    def saldos_asentados_por_cuenta(empresa_id: str) -> list:
        """Solo asientos de comprobantes en estado 'asentado'."""
        pipeline = [
            {"$match": {"empresa_id": empresa_id, "estado": "asentado"}},
            {"$project": {"_id": {"$toString": "$_id"}}},
        ]
        comp_ids = [c["_id"] for c in db["cont_comprobantes"].aggregate(pipeline)]
        if not comp_ids:
            return []
        pipeline2 = [
            {"$match": {"empresa_id": empresa_id, "comprobante_id": {"$in": comp_ids}}},
            {"$group": {
                "_id":      "$cuenta_id",
                "debitos":  {"$sum": "$debito"},
                "creditos": {"$sum": "$credito"},
            }},
            {"$addFields": {
                "saldo": {"$subtract": ["$debitos", "$creditos"]}
            }},
        ]
        return list(db["cont_asientos"].aggregate(pipeline2))

    @staticmethod
    def auxiliar_cuenta(empresa_id: str, cuenta_id: str) -> list:
        """Todos los asientos de una cuenta específica con datos del comprobante."""
        pipeline = [
            {"$match": {"empresa_id": empresa_id, "cuenta_id": cuenta_id}},
            {"$addFields": {
                "comp_oid": {"$convert": {"input": "$comprobante_id", "to": "objectId", "onError": None, "onNull": None}}
            }},
            {"$lookup": {
                "from": "cont_comprobantes",
                "localField": "comp_oid",
                "foreignField": "_id",
                "as": "comprobante",
            }},
            {"$unwind": {"path": "$comprobante", "preserveNullAndEmptyArrays": True}},
            {"$sort": {"comprobante.fecha": 1}},
        ]
        return list(db["cont_asientos"].aggregate(pipeline))

    @staticmethod
    def kpis_dashboard(empresa_id: str) -> dict:
        """Calcula KPIs para el dashboard de contabilidad."""
        # Cartera total pendiente
        pipeline_cartera = [
            {"$match": {"empresa_id": empresa_id, "estado": {"$in": ["vigente", "vencida"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$saldo_pendiente"}, "morosos": {
                "$sum": {"$cond": [{"$eq": ["$estado", "vencida"]}, 1, 0]}
            }}},
        ]
        cartera_res = list(db["cont_cartera"].aggregate(pipeline_cartera))
        total_cartera = cartera_res[0]["total"] if cartera_res else 0
        morosos = cartera_res[0]["morosos"] if cartera_res else 0

        # Facturas por pagar
        pipeline_pagar = [
            {"$match": {"empresa_id": empresa_id, "estado": {"$in": ["pendiente", "aprobada"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$total"}}},
        ]
        pagar_res = list(db["cont_facturas_proveedor"].aggregate(pipeline_pagar))
        total_por_pagar = pagar_res[0]["total"] if pagar_res else 0

        # Pagos próximos (próximos 30 días)
        from datetime import datetime, timedelta
        hoy = datetime.utcnow().date().isoformat()
        en30 = (datetime.utcnow() + timedelta(days=30)).date().isoformat()
        pipeline_proximos = [
            {"$match": {"fecha_pago": {"$gte": hoy, "$lte": en30}, "estado": "pendiente"}},
            {"$group": {"_id": None, "total": {"$sum": "$valor"}, "count": {"$sum": 1}}},
        ]
        proximos_res = list(db["cont_programacion_pagos"].aggregate(pipeline_proximos))
        pagos_proximos = proximos_res[0]["total"] if proximos_res else 0
        pagos_proximos_count = proximos_res[0]["count"] if proximos_res else 0

        # Activos fijos (valor neto)
        pipeline_activos = [
            {"$match": {"empresa_id": empresa_id, "activo": True}},
            {"$group": {
                "_id": None,
                "valor_bruto": {"$sum": "$valor_historico"},
                "dep_acum":    {"$sum": "$depreciacion_acumulada"},
            }},
        ]
        act_res = list(db["cont_activos_fijos"].aggregate(pipeline_activos))
        valor_neto_activos = 0
        if act_res:
            valor_neto_activos = act_res[0]["valor_bruto"] - act_res[0]["dep_acum"]

        return {
            "total_cartera_pendiente": round(total_cartera, 2),
            "total_morosos":           morosos,
            "total_por_pagar":         round(total_por_pagar, 2),
            "pagos_proximos_30_dias":  round(pagos_proximos, 2),
            "pagos_proximos_count":    pagos_proximos_count,
            "valor_neto_activos":      round(valor_neto_activos, 2),
        }
