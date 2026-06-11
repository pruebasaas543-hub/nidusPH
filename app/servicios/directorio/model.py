"""
app/servicios/directorio/model.py
Capa de datos para el módulo Directorio de Contactos.

Colecciones MongoDB:
  directorio_config    – 1 documento por empresa  { empresa_id, bloques:[], limites_bloque:{} }
  directorio_contactos – N documentos por empresa { empresa_id, nombre, bloque, telefonos, ... }
  directorio_bloques   – plantilla global (solo lectura); inicializa nuevas empresas
"""

from app import db
from datetime import datetime
from bson import ObjectId
import base64


BLOQUES_VALIDOS = {"EMERGENCIAS", "ADMIN", "PUBLICOS", "LOGISTICA", "LOCAL", "RESIDENTES"}

_BLOQUES_DEFAULT = [
    {"codigo": "EMERGENCIAS", "nombre": "Emergencias",        "emoji": "🚨", "orden": 1},
    {"codigo": "ADMIN",       "nombre": "Administración",     "emoji": "🏢", "orden": 2},
    {"codigo": "PUBLICOS",    "nombre": "Servicios Públicos", "emoji": "💡", "orden": 3},
    {"codigo": "LOGISTICA",   "nombre": "Logística",          "emoji": "🔧", "orden": 4},
    {"codigo": "LOCAL",       "nombre": "Locales",            "emoji": "📍", "orden": 5},
    {"codigo": "RESIDENTES",  "nombre": "Residentes",         "emoji": "🏠", "orden": 6},
]


def _contactos():  return db["directorio_contactos"]
def _config():     return db["directorio_config"]


def inicializar_plantillas_globales():
    """Siembra directorio_bloques si está vacío. Se llama al arrancar la app."""
    col = db["directorio_bloques"]
    if col.count_documents({}) == 0:
        ahora = datetime.utcnow()
        col.insert_many([
            {**b, "activo": True, "creado_en": ahora, "actualizado_en": ahora}
            for b in _BLOQUES_DEFAULT
        ])


# ── Config por empresa (bloques + límites) ────────────────────────────────────

class DirectorioConfigModel:

    @staticmethod
    def _q(empresa_id: str) -> dict:
        return {"empresa_id": ObjectId(empresa_id)}

    @staticmethod
    def _obtener_doc(empresa_id: str) -> dict:
        return _config().find_one(DirectorioConfigModel._q(empresa_id)) or {}

    @staticmethod
    def inicializar_empresa(empresa_id: str):
        """Crea el doc de config si no existe, copiando las plantillas globales."""
        if _config().count_documents(DirectorioConfigModel._q(empresa_id)) > 0:
            return
        globales = list(db["directorio_bloques"].find({}, {"_id": 0}).sort("orden", 1))
        if not globales:
            globales = _BLOQUES_DEFAULT
        bloques = [
            {
                "codigo":           b["codigo"].upper().strip(),
                "nombre":           b.get("nombre", b["codigo"]).strip(),
                "emoji":            b.get("emoji", ""),
                "orden":            int(b.get("orden", 99)),
                "activo":           True,
                "es_predeterminado": True,
            }
            for b in globales
        ]
        ahora = datetime.utcnow()
        _config().insert_one({
            "empresa_id":     ObjectId(empresa_id),
            "bloques":        bloques,
            "limites_bloque": {},
            "creado_en":      ahora,
            "actualizado_en": ahora,
        })

    # ── Bloques ───────────────────────────────────────────────────────────────

    @staticmethod
    def listar_bloques(empresa_id: str, solo_activos: bool = False) -> list:
        DirectorioConfigModel.inicializar_empresa(empresa_id)
        doc = DirectorioConfigModel._obtener_doc(empresa_id)
        bloques = doc.get("bloques", [])
        if solo_activos:
            bloques = [b for b in bloques if b.get("activo", True)]
        return sorted(bloques, key=lambda b: (b.get("orden", 99), b.get("nombre", "")))

    @staticmethod
    def codigos_activos(empresa_id: str) -> set:
        return {b["codigo"] for b in DirectorioConfigModel.listar_bloques(empresa_id, solo_activos=True)}

    @staticmethod
    def crear_bloque(empresa_id: str, datos: dict) -> str:
        codigo = datos["codigo"].upper().strip()
        doc = DirectorioConfigModel._obtener_doc(empresa_id)
        if any(b["codigo"] == codigo for b in doc.get("bloques", [])):
            raise ValueError(f"Ya existe un bloque con el código {codigo}")
        bloque = {
            "codigo":           codigo,
            "nombre":           datos["nombre"].strip(),
            "emoji":            datos.get("emoji", "").strip(),
            "orden":            int(datos.get("orden") or 99),
            "activo":           True,
            "es_predeterminado": False,
        }
        _config().update_one(
            DirectorioConfigModel._q(empresa_id),
            {"$push": {"bloques": bloque}, "$set": {"actualizado_en": datetime.utcnow()}},
        )
        return codigo

    @staticmethod
    def actualizar_bloque(empresa_id: str, codigo: str, datos: dict):
        _config().update_one(
            {**DirectorioConfigModel._q(empresa_id), "bloques.codigo": codigo},
            {"$set": {
                "bloques.$.nombre":  datos["nombre"].strip(),
                "bloques.$.emoji":   datos.get("emoji", "").strip(),
                "bloques.$.orden":   int(datos.get("orden", 99)),
                "actualizado_en":    datetime.utcnow(),
            }},
        )

    @staticmethod
    def toggle_bloque(empresa_id: str, codigo: str, activo: bool):
        _config().update_one(
            {**DirectorioConfigModel._q(empresa_id), "bloques.codigo": codigo},
            {"$set": {"bloques.$.activo": activo, "actualizado_en": datetime.utcnow()}},
        )

    @staticmethod
    def eliminar_bloque(empresa_id: str, codigo: str) -> bool:
        doc = DirectorioConfigModel._obtener_doc(empresa_id)
        bloque = next((b for b in doc.get("bloques", []) if b["codigo"] == codigo), None)
        if not bloque or bloque.get("es_predeterminado", True):
            return False
        _config().update_one(
            DirectorioConfigModel._q(empresa_id),
            {"$pull": {"bloques": {"codigo": codigo}}, "$set": {"actualizado_en": datetime.utcnow()}},
        )
        return True

    # ── Límites ───────────────────────────────────────────────────────────────

    @staticmethod
    def obtener_limites(empresa_id: str) -> dict:
        return DirectorioConfigModel._obtener_doc(empresa_id).get("limites_bloque", {})

    @staticmethod
    def guardar_limites(empresa_id: str, limites: dict):
        limites_clean = {
            k.upper().strip(): int(v)
            for k, v in limites.items()
            if str(k).strip() and int(v) > 0
        }
        ahora = datetime.utcnow()
        _config().update_one(
            DirectorioConfigModel._q(empresa_id),
            {
                "$set":         {"limites_bloque": limites_clean, "actualizado_en": ahora},
                "$setOnInsert": {"empresa_id": ObjectId(empresa_id), "bloques": [], "creado_en": ahora},
            },
            upsert=True,
        )


# ── Contactos ─────────────────────────────────────────────────────────────────

class ContactoModel:

    @staticmethod
    def crear(datos: dict, empresa_id: str, creado_por: str) -> str:
        doc = {
            "empresa_id":                    ObjectId(empresa_id),
            "bloque":                        datos["bloque"].upper(),
            "nombre":                        datos["nombre"].strip(),
            "cargo_titulo":                  datos.get("cargo_titulo", "").strip(),
            "telefonos":                     datos.get("telefonos", []),
            "correo":                        datos.get("correo", "").strip().lower(),
            "foto_data":                     datos.get("foto_data"),
            "foto_mimetype":                 datos.get("foto_mimetype"),
            "es_visible_para_residentes":    bool(datos.get("es_visible_para_residentes", True)),
            "es_visible_para_seguridad":     bool(datos.get("es_visible_para_seguridad", False)),
            "es_visible_para_administracion":bool(datos.get("es_visible_para_administracion", False)),
            "vinculado_al_boton_de_panico":  bool(datos.get("vinculado_al_boton_de_panico", False)),
            "orden":                         int(datos.get("orden", 0)),
            "activo":                        True,
            "creado_en":                     datetime.utcnow(),
            "creado_por":                    creado_por,
            "actualizado_en":                None,
            # Campos específicos de residentes
            "apellidos":                     (datos.get("apellidos") or "").strip(),
            "tipo_residente":                datos.get("tipo_residente", ""),
            "torre":                         datos.get("torre", ""),
            "apartamento":                   datos.get("apartamento", ""),
            "tiene_parqueadero":             bool(datos.get("tiene_parqueadero", False)),
            "vehiculos":                     datos.get("vehiculos") or [],
        }
        return str(_contactos().insert_one(doc).inserted_id)

    @staticmethod
    def listar_por_empresa(empresa_id: str, solo_activos: bool = True, campo_visibilidad: str = None) -> list:
        filtro = {"empresa_id": ObjectId(empresa_id)}
        if solo_activos:
            filtro["activo"] = True
        if campo_visibilidad:
            filtro[campo_visibilidad] = True
        return list(_contactos().find(filtro).sort([("bloque", 1), ("orden", 1), ("nombre", 1)]))

    @staticmethod
    def obtener(contacto_id: str, empresa_id: str = None):
        try:
            filtro = {"_id": ObjectId(contacto_id)}
            if empresa_id:
                filtro["empresa_id"] = ObjectId(empresa_id)
            return _contactos().find_one(filtro)
        except Exception:
            return None

    @staticmethod
    def actualizar(contacto_id: str, empresa_id: str, datos: dict):
        sets = {
            "bloque":                        datos["bloque"].upper(),
            "nombre":                        datos["nombre"].strip(),
            "cargo_titulo":                  datos.get("cargo_titulo", "").strip(),
            "telefonos":                     datos.get("telefonos", []),
            "correo":                        datos.get("correo", "").strip().lower(),
            "es_visible_para_residentes":    bool(datos.get("es_visible_para_residentes", True)),
            "es_visible_para_seguridad":     bool(datos.get("es_visible_para_seguridad", False)),
            "es_visible_para_administracion":bool(datos.get("es_visible_para_administracion", False)),
            "vinculado_al_boton_de_panico":  bool(datos.get("vinculado_al_boton_de_panico", False)),
            "orden":                         int(datos.get("orden", 0)),
            "activo":                        bool(datos.get("activo", True)),
            "actualizado_en":                datetime.utcnow(),
            # Campos específicos de residentes
            "apellidos":                     (datos.get("apellidos") or "").strip(),
            "tipo_residente":                datos.get("tipo_residente", ""),
            "torre":                         datos.get("torre", ""),
            "apartamento":                   datos.get("apartamento", ""),
            "tiene_parqueadero":             bool(datos.get("tiene_parqueadero", False)),
            "vehiculos":                     datos.get("vehiculos") or [],
        }
        if datos.get("foto_data") is not None:
            sets["foto_data"]     = datos["foto_data"]
            sets["foto_mimetype"] = datos.get("foto_mimetype", "image/jpeg")
        _contactos().update_one(
            {"_id": ObjectId(contacto_id), "empresa_id": ObjectId(empresa_id)},
            {"$set": sets},
        )

    @staticmethod
    def eliminar(contacto_id: str, empresa_id: str):
        try:
            _contactos().delete_one(
                {"_id": ObjectId(contacto_id), "empresa_id": ObjectId(empresa_id)}
            )
        except Exception:
            pass

    @staticmethod
    def contar_por_bloque(empresa_id: str, bloque: str) -> int:
        return _contactos().count_documents({
            "empresa_id": ObjectId(empresa_id),
            "bloque":     bloque,
            "activo":     True,
        })
