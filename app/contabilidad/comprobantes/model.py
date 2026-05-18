"""
app/contabilidad/comprobantes/model.py
──────────────────────────────────────
Operaciones MongoDB para cont_comprobantes y cont_asientos.
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col_comp():
    return db["cont_comprobantes"]


def _col_asientos():
    return db["cont_asientos"]


class ComprobantesModel:

    # ── Comprobantes ─────────────────────────────────────────────────────────

    @staticmethod
    def crear(datos: dict) -> str:
        """Crea un comprobante en estado borrador."""
        # Obtener siguiente número
        ultimo = _col_comp().find_one(
            {"empresa_id": datos["empresa_id"]},
            sort=[("numero", -1)]
        )
        numero = (ultimo["numero"] + 1) if ultimo and ultimo.get("numero") else 1

        doc = {
            "empresa_id": datos["empresa_id"],
            "numero":     numero,
            "tipo":       datos.get("tipo", "manual"),    # manual / auto
            "concepto":   datos.get("concepto", "").strip(),
            "fecha":      datos.get("fecha", datetime.utcnow().date().isoformat()),
            "periodo_id": datos.get("periodo_id"),
            "estado":     "borrador",
            "origen": {
                "modulo": datos.get("origen_modulo", "manual"),
                "ref_id": datos.get("origen_ref_id"),
            },
            "creado_por": datos.get("creado_por", ""),
            "creado_en":  datetime.utcnow(),
        }
        return str(_col_comp().insert_one(doc).inserted_id)

    @staticmethod
    def asentar(comprobante_id: str):
        _col_comp().update_one(
            {"_id": ObjectId(comprobante_id)},
            {"$set": {"estado": "asentado", "asentado_en": datetime.utcnow()}}
        )

    @staticmethod
    def obtener(comprobante_id: str):
        return _col_comp().find_one({"_id": ObjectId(comprobante_id)})

    @staticmethod
    def listar(empresa_id: str, filtros: dict = None) -> list:
        q = {"empresa_id": empresa_id}
        if filtros:
            if filtros.get("fecha_desde"):
                q["fecha"] = q.get("fecha", {})
                q["fecha"]["$gte"] = filtros["fecha_desde"]
            if filtros.get("fecha_hasta"):
                q.setdefault("fecha", {})["$lte"] = filtros["fecha_hasta"]
            if filtros.get("tipo"):
                q["tipo"] = filtros["tipo"]
            if filtros.get("estado"):
                q["estado"] = filtros["estado"]
        return list(_col_comp().find(q).sort("numero", -1))

    # ── Asientos ──────────────────────────────────────────────────────────────

    @staticmethod
    def crear_asiento(comprobante_id: str, linea: dict) -> str:
        doc = {
            "comprobante_id": comprobante_id,
            "cuenta_id":      linea["cuenta_id"],
            "descripcion":    linea.get("descripcion", "").strip(),
            "debito":         float(linea.get("debito", 0)),
            "credito":        float(linea.get("credito", 0)),
            "empresa_id":     linea.get("empresa_id", ""),
        }
        return str(_col_asientos().insert_one(doc).inserted_id)

    @staticmethod
    def obtener_asientos(comprobante_id: str) -> list:
        return list(_col_asientos().find({"comprobante_id": comprobante_id}))

    @staticmethod
    def eliminar_asientos(comprobante_id: str):
        _col_asientos().delete_many({"comprobante_id": comprobante_id})

    @staticmethod
    def sumar_debitos_creditos(comprobante_id: str) -> tuple:
        asientos = ComprobantesModel.obtener_asientos(comprobante_id)
        total_d = sum(a.get("debito", 0) for a in asientos)
        total_c = sum(a.get("credito", 0) for a in asientos)
        return round(total_d, 2), round(total_c, 2)
