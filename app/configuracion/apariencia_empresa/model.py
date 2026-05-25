"""
app/configuracion/apariencia_empresa/model.py
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col():
    return db["apariencia_empresa"]


class AparienciaEmpresaModel:

    @staticmethod
    def listar_por_empresa(empresa_id: str) -> list:
        """Devuelve todos los temas activos asociados a una empresa."""
        try:
            registros = list(_col().find(
                {"empresa_id": ObjectId(empresa_id)}
            ))
            if not registros:
                return []
            # Enriquecer con datos del tema
            apariencia_ids = [r["apariencia_id"] for r in registros]
            temas = {
                str(t["_id"]): t
                for t in db["apariencias"].find({"_id": {"$in": apariencia_ids}})
            }
            resultado = []
            for r in registros:
                t = temas.get(str(r["apariencia_id"]))
                if t:
                    resultado.append({
                        "asoc_id":          str(r["_id"]),
                        "apariencia_id":    str(r["apariencia_id"]),
                        "nombre":           t.get("nombre", ""),
                        "clave":            t.get("clave", ""),
                        "descripcion":      t.get("descripcion", ""),
                        "vista_previa":     t.get("vista_previa", {}),
                        "colores_tarjeta":  t.get("colores_tarjeta", {}),
                        "creado_en":        r.get("creado_en"),
                    })
            return resultado
        except Exception:
            return []

    @staticmethod
    def ids_asociados(empresa_id: str) -> set:
        """Devuelve el set de apariencia_id (str) ya activos para la empresa."""
        try:
            docs = _col().find(
                {"empresa_id": ObjectId(empresa_id)},
                {"apariencia_id": 1}
            )
            return {str(d["apariencia_id"]) for d in docs}
        except Exception:
            return set()

    @staticmethod
    def asociar_multiples(empresa_id: str, apariencia_ids: list, creado_por: str) -> int:
        """Agrega asociaciones para los IDs que aún no estén activos. Devuelve cuántos se insertaron."""
        ya_asociados = AparienciaEmpresaModel.ids_asociados(empresa_id)
        nuevos = [aid for aid in apariencia_ids if aid not in ya_asociados]
        if not nuevos:
            return 0
        docs = [
            {
                "empresa_id":    ObjectId(empresa_id),
                "apariencia_id": ObjectId(aid),
                "creado_en":     datetime.utcnow(),
                "creado_por":    creado_por,
            }
            for aid in nuevos
        ]
        _col().insert_many(docs)
        return len(docs)

    @staticmethod
    def desasociar_uno(empresa_id: str, apariencia_id: str):
        """Elimina la asociación empresa–tema de la colección."""
        try:
            _col().delete_one(
                {"empresa_id": ObjectId(empresa_id), "apariencia_id": ObjectId(apariencia_id)}
            )
        except Exception:
            pass

    @staticmethod
    def listar_con_detalle() -> list:
        """Todas las asociaciones activas enriquecidas (para la tabla resumen)."""
        pipeline = [
            {"$match": {}},
            {"$lookup": {"from": "empresas",    "localField": "empresa_id",    "foreignField": "_id", "as": "empresa"}},
            {"$lookup": {"from": "apariencias", "localField": "apariencia_id", "foreignField": "_id", "as": "apariencia"}},
            {"$unwind": {"path": "$empresa",    "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$apariencia", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id":               {"$toString": "$_id"},
                "empresa_id":        {"$toString": "$empresa_id"},
                "empresa_nombre":    "$empresa.razon_social",
                "apariencia_id":     {"$toString": "$apariencia_id"},
                "apariencia_nombre": "$apariencia.nombre",
                "apariencia_clave":  "$apariencia.clave",
                "creado_en":         1,
                "creado_por":        1,
            }},
            {"$sort": {"empresa_nombre": 1, "apariencia_nombre": 1}},
        ]
        return list(_col().aggregate(pipeline))
