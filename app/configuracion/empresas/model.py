"""
app/configuracion/empresas/model.py
"""

import re
from app import db
from datetime import datetime
from bson import ObjectId
import base64


def _col():  return db["empresas"]
def _col_a(): return db["asociaciones"]
def _col_u(): return db["users"]


def _es_id(s: str) -> bool:
    return bool(re.match(r'^[0-9a-f]{24}$', str(s)))


class EmpresaModel:

    CAMPOS_EDITABLES = {
        "razon_social", "digito_verificacion", "tipo_entidad",
        "departamento", "municipio",
        "direccion", "telefono", "email", "plan", "observaciones", "slug",
        "color_topbar", "color_panel_izq",
    }

    CAMPOS_IMAGEN = ["logo", "carousel_1", "carousel_2", "carousel_3"]

    @staticmethod
    def _imagen_a_doc(file_storage):
        if not file_storage or not file_storage.filename:
            return None
        raw = file_storage.read()
        return {"data": base64.b64encode(raw).decode("utf-8"),
                "mimetype": file_storage.mimetype or "image/jpeg"} if raw else None

    @staticmethod
    def _sin_imagenes() -> dict:
        proj = {}
        for c in EmpresaModel.CAMPOS_IMAGEN:
            proj[f"{c}_data"]     = 0
            proj[f"{c}_mimetype"] = 0
        return proj

    @staticmethod
    def crear(datos: dict, archivos: dict, creado_por: str) -> str:
        imgs = {}
        for c in EmpresaModel.CAMPOS_IMAGEN:
            img = EmpresaModel._imagen_a_doc(archivos.get(c))
            imgs[f"{c}_data"]     = img["data"]     if img else None
            imgs[f"{c}_mimetype"] = img["mimetype"] if img else None

        slug = datos.get("slug", "").strip().lower().replace(" ", "-") or \
               datos["razon_social"].strip().lower().replace(" ", "-")

        doc = {
            "nit":                 datos["nit"].strip(),
            "digito_verificacion": datos.get("digito_verificacion", "").strip(),
            "razon_social":        datos["razon_social"].strip(),
            "tipo_entidad":        datos.get("tipo_entidad", "").strip(),
            "slug":                slug,
            "departamento":        datos.get("departamento", "").strip(),
            "municipio":           datos.get("municipio", "").strip(),
            "direccion":           datos.get("direccion", "").strip(),
            "telefono":            datos.get("telefono", "").strip(),
            "email":               datos["email"].strip().lower(),
            "plan":                datos.get("plan", "").strip(),
            "color_topbar":        datos.get("color_topbar",    "#0a1250").strip(),
            "color_panel_izq":     datos.get("color_panel_izq", "#080e2e").strip(),
            **imgs,
            "observaciones":       datos.get("observaciones", "").strip(),
            "activo":              True,
            "creado_en":           datetime.utcnow(),
            "creado_por":          creado_por,
            "actualizado_en":      None,
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def migrar_plan_a_id():
        """Convierte empresa.plan de nombre/slug a str(_id) del plan. Idempotente."""
        planes = list(db["planes_saas"].find({}, {"_id": 1, "nombre": 1, "plan_id": 1}))
        nombre_a_id  = {p["nombre"]:   str(p["_id"]) for p in planes}
        slug_a_id    = {p.get("plan_id", ""): str(p["_id"]) for p in planes if p.get("plan_id")}
        for emp in _col().find({"plan": {"$exists": True, "$ne": ""}}):
            plan_val = emp.get("plan", "")
            if plan_val and not _es_id(plan_val):
                nuevo_id = nombre_a_id.get(plan_val) or slug_a_id.get(plan_val)
                if nuevo_id:
                    _col().update_one({"_id": emp["_id"]}, {"$set": {"plan": nuevo_id}})

    @staticmethod
    def listar(solo_activas=False) -> list:
        EmpresaModel.migrar_plan_a_id()
        filtro = {"activo": True} if solo_activas else {}
        return list(_col().find(filtro, EmpresaModel._sin_imagenes()).sort("razon_social", 1))

    @staticmethod
    def buscar_por_id(empresa_id: str, con_imagenes=False):
        try:
            oid = ObjectId(empresa_id)
        except Exception:
            return None
        proj = None if con_imagenes else EmpresaModel._sin_imagenes()
        return _col().find_one({"_id": oid}, proj)

    @staticmethod
    def buscar_por_nit(nit: str):
        return _col().find_one({"nit": nit.strip()})

    @staticmethod
    def buscar_por_slug(slug: str):
        return _col().find_one({"slug": slug.strip().lower()})

    @staticmethod
    def actualizar(empresa_id: str, datos: dict, archivos=None):
        update = {k: v for k, v in datos.items() if k in EmpresaModel.CAMPOS_EDITABLES}
        if "slug" in update:
            update["slug"] = update["slug"].lower().replace(" ", "-")
        if archivos:
            for c in EmpresaModel.CAMPOS_IMAGEN:
                img = EmpresaModel._imagen_a_doc(archivos.get(c))
                if img:
                    update[f"{c}_data"]     = img["data"]
                    update[f"{c}_mimetype"] = img["mimetype"]
        update["actualizado_en"] = datetime.utcnow()
        _col().update_one({"_id": ObjectId(empresa_id)}, {"$set": update})

    @staticmethod
    def cambiar_estado(empresa_id: str, activo: bool):
        _col().update_one(
            {"_id": ObjectId(empresa_id)},
            {"$set": {"activo": activo, "actualizado_en": datetime.utcnow()}}
        )
        # Activar/desactivar las asociaciones de esta empresa para reflejar su estado
        _col_a().update_many(
            {"empresa_id": ObjectId(empresa_id)},
            {"$set": {"activo": activo}}
        )

    @staticmethod
    def obtener_imagen(empresa_id: str, campo: str):
        try:
            oid = ObjectId(empresa_id)
        except Exception:
            return None
        doc = _col().find_one({"_id": oid}, {f"{campo}_data": 1, f"{campo}_mimetype": 1})
        if not doc or not doc.get(f"{campo}_data"):
            return None
        return {"data": doc[f"{campo}_data"], "mimetype": doc[f"{campo}_mimetype"]}
