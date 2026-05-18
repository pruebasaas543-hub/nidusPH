"""
app/contabilidad/tesoreria/model.py
─────────────────────────────────────
Operaciones MongoDB para facturas proveedor, aprobaciones y programación de pagos.
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col_facturas():
    return db["cont_facturas_proveedor"]


def _col_aprobaciones():
    return db["cont_aprobaciones"]


def _col_programacion():
    return db["cont_programacion_pagos"]


class TesoreriaModel:

    # ── Facturas proveedor ────────────────────────────────────────────────────

    @staticmethod
    def crear_factura(datos: dict) -> str:
        doc = {
            "empresa_id":    datos["empresa_id"],
            "proveedor_nit": datos.get("proveedor_nit", "").strip(),
            "numero":        datos.get("numero", "").strip(),
            "fecha":         datos.get("fecha", datetime.utcnow().date().isoformat()),
            "subtotal":      float(datos.get("subtotal", 0)),
            "impuestos":     float(datos.get("impuestos", 0)),
            "retenciones":   float(datos.get("retenciones", 0)),
            "total":         float(datos.get("total", 0)),
            "estado":        "pendiente",    # pendiente / aprobada / pagada / anulada
            "creado_en":     datetime.utcnow(),
        }
        return str(_col_facturas().insert_one(doc).inserted_id)

    @staticmethod
    def obtener_factura(factura_id: str):
        return _col_facturas().find_one({"_id": ObjectId(factura_id)})

    @staticmethod
    def listar_facturas(empresa_id: str) -> list:
        return list(_col_facturas().find({"empresa_id": empresa_id}).sort("fecha", -1))

    @staticmethod
    def cambiar_estado_factura(factura_id: str, estado: str):
        _col_facturas().update_one(
            {"_id": ObjectId(factura_id)},
            {"$set": {"estado": estado, "actualizado_en": datetime.utcnow()}}
        )

    # ── Aprobaciones ──────────────────────────────────────────────────────────

    @staticmethod
    def crear_aprobacion(factura_id: str, aprobado_por: str, estado: str) -> str:
        doc = {
            "factura_id":   factura_id,
            "estado":       estado,
            "aprobado_por": aprobado_por,
            "fecha":        datetime.utcnow(),
        }
        return str(_col_aprobaciones().insert_one(doc).inserted_id)

    # ── Programación de pagos ─────────────────────────────────────────────────

    @staticmethod
    def programar_pago(datos: dict) -> str:
        doc = {
            "factura_id": datos["factura_id"],
            "fecha_pago": datos.get("fecha_pago"),
            "valor":      float(datos.get("valor", 0)),
            "estado":     "pendiente",
            "creado_en":  datetime.utcnow(),
        }
        return str(_col_programacion().insert_one(doc).inserted_id)

    @staticmethod
    def listar_programacion(empresa_id: str) -> list:
        # Join facturas → programación
        pipeline = [
            {"$match": {"empresa_id": empresa_id}},
            {"$lookup": {
                "from": "cont_programacion_pagos",
                "localField": "_id_str",
                "foreignField": "factura_id",
                "as": "programacion",
            }},
        ]
        # Simpler approach: get all programacion for facturas of this empresa
        facturas = list(_col_facturas().find({"empresa_id": empresa_id}, {"_id": 1}))
        factura_ids = [str(f["_id"]) for f in facturas]
        return list(_col_programacion().find({"factura_id": {"$in": factura_ids}}).sort("fecha_pago", 1))
