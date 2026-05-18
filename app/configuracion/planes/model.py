"""
app/configuracion/planes/model.py
─────────────────────────────────
CRUD de planes SaaS.
"""

import re
import base64
from app import db
from datetime import datetime
from bson import ObjectId


def _col(): return db["planes_saas"]


def _es_id(s: str) -> bool:
    return bool(re.match(r'^[0-9a-f]{24}$', str(s)))


def _generar_plan_id(nombre: str) -> str:
    """Genera un plan_id único a partir del nombre + timestamp actual en base64."""
    ts  = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    raw = f"{nombre.strip()}_{ts}".encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    # Dejar solo alfanuméricos y truncar a 24 caracteres
    return "".join(c for c in b64.lower() if c.isalnum())[:24]


class PlanModel:

    CAMPOS_EDITABLES = {
        "nombre", "descripcion", "modulos_incluidos", "limites",
        "precio", "destacado", "orden", "estado",
    }

    @staticmethod
    def listar(solo_activos=False) -> list:
        PlanModel.migrar_campos_legado()
        PlanModel.migrar_modulos_a_ids()
        PlanModel.migrar_estado_a_id()
        PlanModel.migrar_pais_a_id()
        PlanModel.migrar_soporte_a_id()
        filtro = {}
        if solo_activos:
            activo = db["estado_planes"].find_one({"nombre": "activo"})
            if activo:
                filtro = {"estado": str(activo["_id"])}
            else:
                filtro = {"estado": "activo"}
        return list(_col().find(filtro).sort("orden", 1))

    @staticmethod
    def buscar_por_id(plan_id):
        try:
            return _col().find_one({"_id": ObjectId(plan_id)})
        except Exception:
            return None

    @staticmethod
    def buscar_por_slug(plan_id_slug: str):
        return _col().find_one({"plan_id": plan_id_slug.strip().lower()})

    @staticmethod
    def crear(datos: dict, creado_por: str) -> str:
        nombre = datos["nombre"].strip()
        doc = {
            # _id lo asigna MongoDB automáticamente
            "plan_id":           _generar_plan_id(nombre),
            "nombre":            nombre,
            "descripcion":       datos.get("descripcion", "").strip(),
            "modulos_incluidos": datos.get("modulos_incluidos", []),
            "limites": {
                "max_usuarios_ph":    int(datos.get("limites", {}).get("max_usuarios_ph",    0)),
                "max_usuarios_admin": int(datos.get("limites", {}).get("max_usuarios_admin", 0)),
                "soporte":            datos.get("limites", {}).get("soporte", []),
            },
            "precio": {
                "valor_copropiedad": float(datos.get("precio", {}).get("valor_copropiedad", 0)),
                "pais":              datos.get("precio", {}).get("pais",   "").strip(),
                "moneda":            datos.get("precio", {}).get("moneda", "").strip(),
            },
            "destacado":      bool(datos.get("destacado", False)),
            "orden":          int(datos.get("orden", 99)),
            "estado":         datos.get("estado", "activo"),
            "creado_en":      datetime.utcnow(),
            "creado_por":     creado_por,
            "actualizado_en": None,
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def actualizar(plan_id: str, datos: dict):
        update = {k: v for k, v in datos.items() if k in PlanModel.CAMPOS_EDITABLES}
        update["actualizado_en"] = datetime.utcnow()
        _col().update_one({"_id": ObjectId(plan_id)}, {"$set": update})

    @staticmethod
    def eliminar(plan_id: str):
        _col().delete_one({"_id": ObjectId(plan_id)})

    @staticmethod
    def modulos_de_plan(plan_id_str: str) -> list:
        """Recibe el str(_id) del plan y retorna sus modulos_incluidos."""
        plan = PlanModel.buscar_por_id(plan_id_str)
        return plan.get("modulos_incluidos", []) if plan else []

    @staticmethod
    def migrar_estado_a_id():
        """Convierte planes_saas.estado de nombre ('activo'/'archivado') a str(_id). Idempotente."""
        col_e = db["estado_planes"]
        # Asegurar que existen los documentos de estado
        for nombre in ("activo", "archivado"):
            if not col_e.find_one({"nombre": nombre}):
                col_e.insert_one({"nombre": nombre})
        nombre_a_id = {e["nombre"]: str(e["_id"]) for e in col_e.find({})}
        for doc in _col().find({}):
            val = doc.get("estado", "")
            if val and not _es_id(val):
                nuevo = nombre_a_id.get(val)
                if nuevo:
                    _col().update_one({"_id": doc["_id"]}, {"$set": {"estado": nuevo}})

    @staticmethod
    def migrar_pais_a_id():
        """Convierte planes_saas.precio.pais de pais_uso a str(_id) de tipo_moneda. Idempotente."""
        monedas = list(db["tipo_moneda"].find({}, {"_id": 1, "pais_uso": 1}))
        if not monedas:
            return
        pais_a_id = {m["pais_uso"]: str(m["_id"]) for m in monedas}
        for doc in _col().find({"precio.pais": {"$exists": True, "$ne": ""}}):
            val = doc.get("precio", {}).get("pais", "")
            if val and not _es_id(val):
                nuevo = pais_a_id.get(val)
                if nuevo:
                    _col().update_one({"_id": doc["_id"]}, {"$set": {"precio.pais": nuevo}})

    @staticmethod
    def migrar_soporte_a_id():
        """Convierte limites.soporte de id_canal strings a str(_id) de canales_soporte. Idempotente."""
        canales = list(db["canales_soporte"].find({}, {"_id": 1, "id_canal": 1}))
        if not canales:
            return
        canal_a_id = {c["id_canal"]: str(c["_id"]) for c in canales}
        for doc in _col().find({"limites.soporte": {"$exists": True, "$ne": []}}):
            soporte = doc.get("limites", {}).get("soporte", [])
            if any(not _es_id(s) for s in soporte):
                nuevos = [canal_a_id.get(s, s) for s in soporte]
                _col().update_one({"_id": doc["_id"]}, {"$set": {"limites.soporte": nuevos}})

    @staticmethod
    def migrar_modulos_a_ids():
        """Convierte modulos_incluidos de nombres de servicio a str(_id). Idempotente."""
        from app.servicios.model import ServicioModel
        servicios = ServicioModel.listar(solo_activos=False)
        nombre_a_id = {s["nombre"]: str(s["_id"]) for s in servicios}
        for doc in _col().find({"modulos_incluidos": {"$exists": True, "$ne": []}}):
            modulos = doc.get("modulos_incluidos", [])
            if any(not _es_id(m) for m in modulos):
                nuevos = [nombre_a_id.get(m, m) for m in modulos]
                _col().update_one({"_id": doc["_id"]}, {"$set": {"modulos_incluidos": nuevos}})

    @staticmethod
    def migrar_campos_legado():
        """
        Migra documentos con nombres de campos anteriores al esquema actual.
        Es idempotente: si ya no existen los campos viejos, no hace nada.
        """
        # precio.mensual → precio.valor_copropiedad
        _col().update_many(
            {"precio.mensual": {"$exists": True}},
            {"$rename": {"precio.mensual": "precio.valor_copropiedad"}}
        )
        # limites.max_unidades → limites.max_usuarios_ph
        _col().update_many(
            {"limites.max_unidades": {"$exists": True}},
            {"$rename": {"limites.max_unidades": "limites.max_usuarios_ph"}}
        )
        # Eliminar campos obsoletos
        _col().update_many(
            {"$or": [
                {"precio.anual":        {"$exists": True}},
                {"limites.max_almac_mb": {"$exists": True}},
            ]},
            {"$unset": {"precio.anual": "", "limites.max_almac_mb": ""}}
        )
        # soporte: si es string convertir a lista
        for doc in _col().find({"limites.soporte": {"$type": "string"}}):
            val = doc["limites"].get("soporte", "")
            _col().update_one(
                {"_id": doc["_id"]},
                {"$set": {"limites.soporte": [val] if val else []}}
            )
        # soporte: si está anidado [[...]] aplanar a [...]
        for doc in _col().find({"limites.soporte.0": {"$type": "array"}}):
            nested = doc["limites"].get("soporte", [])
            flat = [item for sub in nested for item in (sub if isinstance(sub, list) else [sub])]
            _col().update_one(
                {"_id": doc["_id"]},
                {"$set": {"limites.soporte": flat}}
            )
