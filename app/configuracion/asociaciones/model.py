"""
app/configuracion/asociaciones/model.py
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col():  return db["asociaciones"]
def _col_u(): return db["users"]

def _roles_sistema():
    from app.configuracion.roles.model import RolModel
    return RolModel.nombres_sistema()


class AsociacionModel:

    @staticmethod
    def vincular(user_id, empresa_id, rol_asignado, unidad, creado_por,
                 torre="", apartamento="",
                 nombre_contacto_emergencia="", telefono_contacto_emergencia="") -> str:
        # GUARD: siempre almacenar nombre, nunca ObjectId
        from app.configuracion.roles.model import RolModel
        rol_asignado = RolModel.id_a_nombre(str(rol_asignado))

        empresa_oid = ObjectId(empresa_id) if empresa_id else None
        existente = _col().find_one(
            {"user_id": ObjectId(user_id), "empresa_id": empresa_oid, "activo": True}
        )
        if existente:
            return str(existente["_id"])
        doc = {
            "user_id":                      ObjectId(user_id),
            "empresa_id":                   empresa_oid,
            "rol_asignado":                 rol_asignado,
            "unidad":                       (unidad or "").strip(),
            "torre":                        (torre or "").strip(),
            "apartamento":                  (apartamento or "").strip(),
            "nombre_contacto_emergencia":   (nombre_contacto_emergencia or "").strip(),
            "telefono_contacto_emergencia": (telefono_contacto_emergencia or "").strip(),
            "activo":                       True,
            "creado_en":                    datetime.utcnow(),
            "creado_por":                   creado_por,
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def _lookup_rol_pipeline() -> list:
        """Sub-pipeline que resuelve rol_asignado (ID) a nombre via roles."""
        return [
            {"$addFields": {
                "_rol_oid": {"$cond": [
                    {"$regexMatch": {"input": "$rol_asignado", "regex": "^[0-9a-f]{24}$"}},
                    {"$toObjectId": "$rol_asignado"},
                    None,
                ]},
            }},
            {"$lookup": {
                "from": "roles",
                "localField": "_rol_oid",
                "foreignField": "_id",
                "as": "_rol_doc",
            }},
            {"$addFields": {
                "rol_nombre": {"$ifNull": [
                    {"$arrayElemAt": ["$_rol_doc.nombre", 0]},
                    "$rol_asignado",
                ]},
            }},
            {"$project": {"_rol_oid": 0, "_rol_doc": 0}},
        ]

    @staticmethod
    def listar_todas() -> list:
        proj = {}
        for c in ["carousel_1", "carousel_2", "carousel_3", "logo"]:
            proj[f"{c}_data"]     = 0
            proj[f"{c}_mimetype"] = 0
        sin_img = [{"$project": proj}]
        pipeline = [
            {"$match": {"activo": True, "empresa_id": {"$ne": None}}},
            {"$lookup": {"from": "users",    "localField": "user_id",    "foreignField": "_id", "as": "usuario"}},
            {"$lookup": {"from": "empresas", "localField": "empresa_id", "foreignField": "_id", "as": "empresa", "pipeline": sin_img}},
            {"$unwind": {"path": "$usuario", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$empresa",  "preserveNullAndEmptyArrays": True}},
            *AsociacionModel._lookup_rol_pipeline(),
            {"$sort": {"creado_en": -1}},
        ]
        return list(_col().aggregate(pipeline))

    @staticmethod
    def listar_por_empresa(empresa_id) -> list:
        pipeline = [
            {"$match": {"empresa_id": ObjectId(empresa_id), "activo": True}},
            {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "usuario"}},
            {"$unwind": {"path": "$usuario", "preserveNullAndEmptyArrays": True}},
            *AsociacionModel._lookup_rol_pipeline(),
        ]
        return list(_col().aggregate(pipeline))

    @staticmethod
    def usuarios_sin_empresa() -> list:
        # Excluir solo usuarios con rol de sistema (empresa_id: null)
        ids_sistema = _col().distinct("user_id", {"activo": True, "empresa_id": None})
        excluir_oids = [ObjectId(i) for i in ids_sistema]
        return list(_col_u().find(
            {"_id": {"$nin": excluir_oids}, "activo": True},
            {"nombres": 1, "apellidos": 1, "tipo_documento": 1, "numero_documento": 1}
        ))

    @staticmethod
    def listar_por_usuario(user_id) -> list:
        pipeline = [
            {"$match": {"user_id": ObjectId(user_id), "activo": True, "empresa_id": {"$ne": None}}},
            {"$lookup": {
                "from": "empresas",
                "localField": "empresa_id",
                "foreignField": "_id",
                "as": "empresa",
            }},
            {"$unwind": {"path": "$empresa", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "_id": 1,
                "empresa_id": 1,
                "empresa_nombre": "$empresa.razon_social",
                "rol_asignado": 1,
            }},
            {"$sort": {"empresa_nombre": 1}},
        ]
        return list(_col().aggregate(pipeline))

    @staticmethod
    def editar_rol(asoc_id: str, rol_nombre: str):
        from datetime import datetime
        _col().update_one(
            {"_id": ObjectId(asoc_id)},
            {"$set": {"rol_asignado": rol_nombre, "actualizado_en": datetime.utcnow()}}
        )

    @staticmethod
    def desactivar(asoc_id):
        _col().delete_one({"_id": ObjectId(asoc_id)})
