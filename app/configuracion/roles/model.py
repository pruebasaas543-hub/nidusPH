"""
app/configuracion/roles/model.py
"""

import re
from app import db
from datetime import datetime
from bson import ObjectId


def _es_id(s: str) -> bool:
    return bool(re.match(r'^[0-9a-f]{24}$', str(s)))

MODULOS_SISTEMA = [
    "Documentos", "Pagos", "PQRS", "Reservas", "Asambleas",
    "Cartera", "Facturación", "Nómina", "Control Acceso", "Comunicados",
]

# Nombres que siempre tienen acceso de sistema — fallback si la BD no tiene es_sistema
_NOMBRES_SISTEMA_FIJOS = {"SuperAdmin", "AdministradorImplementador", "ImplementadorNidus"}

def _col():      return db["roles"]
def _col_hab():  return db["habilitacion_roles"]


def ROLES_PROTEGIDOS() -> set:
    return {r["nombre"] for r in _col().find({"es_sistema": True}, {"nombre": 1})}


class RolModel:

    @staticmethod
    def nombres_sistema() -> set:
        """Retorna roles de sistema desde BD; usa fallback hardcodeado si la BD
        no tiene el campo es_sistema configurado (migración pendiente)."""
        desde_bd = {r["nombre"] for r in _col().find({"es_sistema": True}, {"nombre": 1})}
        if desde_bd:
            return desde_bd
        # Fallback: marcar roles base en BD y devolver los fijos
        RolModel._marcar_roles_sistema()
        return _NOMBRES_SISTEMA_FIJOS

    @staticmethod
    def _marcar_roles_sistema():
        """Migración idempotente: añade es_sistema:True a los roles fijos del SaaS."""
        _col().update_many(
            {"nombre": {"$in": list(_NOMBRES_SISTEMA_FIJOS)}},
            {"$set": {"es_sistema": True}}
        )

    @staticmethod
    def id_a_nombre(valor: str) -> str:
        """Convierte un ObjectId de rol a su nombre. Si ya es nombre, lo retorna tal cual.
        Uso obligatorio antes de cualquier escritura de rol_asignado en asociaciones."""
        if not valor:
            return ""
        if _es_id(str(valor)):
            doc = _col().find_one({"_id": ObjectId(str(valor))}, {"nombre": 1})
            return doc["nombre"] if doc else str(valor)
        return str(valor)

    @staticmethod
    def migrar_asociaciones_ids_a_nombres():
        """Migración idempotente: reemplaza ObjectIds en rol_asignado por nombres de rol.
        Se ejecuta al iniciar la app. Es segura de correr múltiples veces."""
        import re
        _RE = re.compile(r'^[0-9a-f]{24}$', re.I)
        col_asoc = db["asociaciones"]
        docs = list(col_asoc.find(
            {"rol_asignado": {"$regex": "^[0-9a-f]{24}$"}},
            {"_id": 1, "rol_asignado": 1}
        ))
        if not docs:
            return 0
        roles = {str(r["_id"]): r["nombre"] for r in _col().find({}, {"nombre": 1})}
        actualizados = 0
        for doc in docs:
            rol_id = str(doc["rol_asignado"])
            nombre = roles.get(rol_id)
            if nombre:
                col_asoc.update_one({"_id": doc["_id"]}, {"$set": {"rol_asignado": nombre}})
                actualizados += 1
        return actualizados

    @staticmethod
    def inicializar_roles_base(creado_por="sistema"):
        base = [
            {"nombre": "SuperAdmin",              "descripcion": "Control total del SaaS",          "modulos": MODULOS_SISTEMA, "es_sistema": True},
            {"nombre": "AdministradorImplementador", "descripcion": "Tecnico de implementacion",    "modulos": MODULOS_SISTEMA, "es_sistema": True},
            {"nombre": "AdminCliente",            "descripcion": "Administra un conjunto",           "modulos": ["Pagos","PQRS","Reservas","Asambleas","Cartera","Facturación","Comunicados"]},
            {"nombre": "AdministradorPH",         "descripcion": "Gestion operativa",               "modulos": ["PQRS","Reservas","Control Acceso","Comunicados"]},
            {"nombre": "Residente",               "descripcion": "Propietario o arrendatario",      "modulos": ["Pagos","PQRS","Reservas","Comunicados"]},
            {"nombre": "Visitante",               "descripcion": "Acceso temporal",                 "modulos": ["Comunicados"]},
        ]
        for r in base:
            existente = _col().find_one({"nombre": r["nombre"]})
            if not existente:
                _col().insert_one(
                    {**r, "activo": True, "creado_en": datetime.utcnow(), "creado_por": creado_por}
                )
            elif r.get("es_sistema") and not existente.get("es_sistema"):
                # Migración: añadir es_sistema a roles ya existentes
                _col().update_one({"_id": existente["_id"]}, {"$set": {"es_sistema": True}})

    @staticmethod
    def migrar_modulos_a_ids():
        """Convierte modulos de nombres de servicio a str(_id). Idempotente."""
        from app.servicios.model import ServicioModel
        servicios = ServicioModel.listar(solo_activos=False)
        nombre_a_id = {s["nombre"]: str(s["_id"]) for s in servicios}
        for doc in _col().find({"modulos": {"$exists": True, "$ne": []}}):
            modulos = doc.get("modulos", [])
            if any(not _es_id(m) for m in modulos):
                nuevos = [nombre_a_id.get(m, m) for m in modulos]
                _col().update_one({"_id": doc["_id"]}, {"$set": {"modulos": nuevos}})

    @staticmethod
    def listar(solo_activos=True, excluir_internos=False) -> list:
        RolModel.migrar_modulos_a_ids()
        RolModel.migrar_eliminar_nivel()
        filtro = {}
        if solo_activos:
            filtro["activo"] = True
        if excluir_internos:
            filtro["es_sistema"] = {"$ne": True}
        return list(_col().find(filtro).sort("nombre", 1))

    @staticmethod
    def buscar_por_id(rol_id):
        try:
            return _col().find_one({"_id": ObjectId(rol_id)})
        except Exception:
            return None

    @staticmethod
    def buscar_por_nombre(nombre):
        return _col().find_one({"nombre": nombre})

    @staticmethod
    def crear(datos: dict, creado_por: str) -> str:
        doc = {
            "nombre":       datos["nombre"].strip(),
            "descripcion":  datos.get("descripcion", "").strip(),
            "modulos":      datos.get("modulos", []),
            "activo":       True,
            "creado_en":    datetime.utcnow(),
            "creado_por":   creado_por,
            "actualizado_en": None,
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def actualizar(rol_id: str, datos: dict):
        datos["actualizado_en"] = datetime.utcnow()
        _col().update_one({"_id": ObjectId(rol_id)}, {"$set": datos})

    @staticmethod
    def eliminar(rol_id: str) -> bool:
        rol = _col().find_one({"_id": ObjectId(rol_id)})
        if not rol or rol.get("es_sistema"):
            return False
        _col().delete_one({"_id": ObjectId(rol_id)})
        return True

    @staticmethod
    def migrar_eliminar_nivel():
        """Elimina el campo 'nivel' de todos los documentos. Idempotente."""
        _col().update_many(
            {"nivel": {"$exists": True}},
            {"$unset": {"nivel": ""}}
        )


class HabilitacionRolModel:

    @staticmethod
    def _ids_roles_default() -> list:
        """Devuelve los IDs de los roles por defecto (AdminCliente, AdministradorPH, Residente)."""
        nombres = ["AdminCliente", "AdministradorPH", "Residente"]
        ids = []
        for nombre in nombres:
            r = _col().find_one({"nombre": nombre}, {"_id": 1})
            if r:
                ids.append(str(r["_id"]))
        return ids

    @staticmethod
    def migrar_roles_activos_a_ids():
        """Convierte habilitacion_roles.roles_activos de nombres a str(_id). Idempotente."""
        roles = list(_col().find({}, {"_id": 1, "nombre": 1}))
        nombre_a_id = {r["nombre"]: str(r["_id"]) for r in roles}
        for doc in _col_hab().find({"roles_activos": {"$exists": True, "$ne": []}}):
            activos = doc.get("roles_activos", [])
            if any(not _es_id(str(a)) for a in activos):
                nuevos = [nombre_a_id.get(a, a) for a in activos]
                _col_hab().update_one({"_id": doc["_id"]}, {"$set": {"roles_activos": nuevos}})

    @staticmethod
    def obtener_para_empresa(empresa_id):
        return _col_hab().find_one({"empresa_id": ObjectId(empresa_id)})

    @staticmethod
    def guardar(empresa_id: str, roles_activos: list, actualizado_por: str):
        _col_hab().update_one(
            {"empresa_id": ObjectId(empresa_id)},
            {"$set": {
                "empresa_id":      ObjectId(empresa_id),
                "roles_activos":   roles_activos,
                "actualizado_en":  datetime.utcnow(),
                "actualizado_por": actualizado_por,
            }},
            upsert=True
        )

    @staticmethod
    def roles_activos_para_empresa(empresa_id: str) -> list:
        doc = HabilitacionRolModel.obtener_para_empresa(empresa_id)
        return doc.get("roles_activos", []) if doc else HabilitacionRolModel._ids_roles_default()
