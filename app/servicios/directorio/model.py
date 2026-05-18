"""
app/servicios/directorio/model.py
Capa de datos para el módulo Directorio de Funcionarios y Órganos de Control.

Colecciones MongoDB:
  directorio_cargos        – configuración paramétrica de cargos
  directorio_funcionarios  – perfiles de funcionarios; referencia a cargos via cargo_id
"""

import json
from app import db
from datetime import datetime
from bson import ObjectId


def _cargos():       return db["directorio_cargos"]
def _funcionarios(): return db["directorio_funcionarios"]


def _horario_desde(datos: dict):
    """
    Extrae y normaliza el sub-documento horario desde el payload recibido.
    Acepta tanto la clave 'horario' (objeto anidado) como campos planos
    del formulario por retrocompatibilidad. Devuelve None si no hay datos.
    """
    raw = datos.get("horario")
    if isinstance(raw, str):
        try:    raw = json.loads(raw)
        except: raw = {}
    if not isinstance(raw, dict):
        raw = {}

    dias_raw = raw.get("dias", {})
    if isinstance(dias_raw, str):
        try:    dias_raw = json.loads(dias_raw)
        except: dias_raw = {}

    horario = {
        "empresa_proveedora": (raw.get("empresa_proveedora") or "").strip(),
        "tipo_turno":         (raw.get("tipo_turno")         or "").strip(),
        "hora_entrada":       (raw.get("hora_entrada")       or "").strip(),
        "hora_salida":        (raw.get("hora_salida")        or "").strip(),
        "puesto_asignado":    (raw.get("puesto_asignado")    or "").strip(),
        "dias": {
            dia: (dias_raw.get(dia) or None)
            for dia in ("lunes","martes","miercoles","jueves","viernes","sabado","domingo")
        },
    }
    # Si todos los campos están vacíos y no hay días asignados, no guardamos nada
    cualquier_valor = any([
        horario["empresa_proveedora"], horario["tipo_turno"],
        horario["hora_entrada"],       horario["hora_salida"],
        horario["puesto_asignado"],
        any(v for v in horario["dias"].values()),
    ])
    return horario if cualquier_valor else None


# ── CARGOS ────────────────────────────────────────────────────────────────

class CargoModel:

    @staticmethod
    def crear(datos: dict, creado_por: str) -> str:
        doc = {
            "nombre":           datos["nombre"].strip(),
            "categoria":        datos.get("categoria", "Administración").strip(),
            "requiere_horario": bool(datos.get("requiere_horario", False)),
            "activo":           True,
            "creado_en":        datetime.utcnow(),
            "creado_por":       creado_por,
            "actualizado_en":   None,
        }
        return str(_cargos().insert_one(doc).inserted_id)

    @staticmethod
    def listar(solo_activos: bool = True) -> list:
        filtro = {"activo": True} if solo_activos else {}
        return list(_cargos().find(filtro).sort("nombre", 1))

    @staticmethod
    def obtener(cargo_id: str):
        try:
            return _cargos().find_one({"_id": ObjectId(cargo_id)})
        except Exception:
            return None

    @staticmethod
    def obtener_por_nombre(nombre: str):
        return _cargos().find_one({"nombre": nombre.strip()})

    @staticmethod
    def actualizar(cargo_id: str, datos: dict):
        _cargos().update_one(
            {"_id": ObjectId(cargo_id)},
            {"$set": {
                "nombre":           datos["nombre"].strip(),
                "categoria":        datos.get("categoria", "Administración").strip(),
                "requiere_horario": bool(datos.get("requiere_horario", False)),
                "actualizado_en":   datetime.utcnow(),
            }}
        )

    @staticmethod
    def cambiar_estado(cargo_id: str, activo: bool):
        _cargos().update_one(
            {"_id": ObjectId(cargo_id)},
            {"$set": {"activo": activo, "actualizado_en": datetime.utcnow()}}
        )

    @staticmethod
    def en_uso(cargo_id: str) -> bool:
        return _funcionarios().count_documents({"cargo_id": cargo_id, "activo": True}) > 0


# ── FUNCIONARIOS ──────────────────────────────────────────────────────────

class FuncionarioModel:

    @staticmethod
    def crear(datos: dict, creado_por: str, ip: str) -> str:
        """
        Estructura del documento:
          - datos generales (planos)
          - cargo_id  →  referencia a directorio_cargos._id  (string)
          - horario   →  sub-documento con campos de turno y dias{}
          - habeas_data_*  →  auditoría de consentimiento (RN-DIR-01)
        """
        doc = {
            "nombres":         datos["nombres"].strip(),
            "apellidos":       datos["apellidos"].strip(),
            "cargo_id":        datos["cargo_id"].strip(),
            "cargo_nombre":    datos.get("cargo_nombre", "").strip(),
            "cargo_categoria": datos.get("cargo_categoria", "").strip(),
            "telefono":        datos.get("telefono", "").strip(),
            "email":           datos.get("email", "").strip().lower(),
            "fecha_inicio":    datos.get("fecha_inicio", "").strip(),
            # Sub-documento de horario (None si cargo no lo requiere)
            "horario":         _horario_desde(datos),
            # Habeas data — RN-DIR-01
            "habeas_data_aceptado": True,
            "habeas_data_fecha":    datetime.utcnow(),
            "habeas_data_ip":       ip,
            # Estado
            "activo":         True,
            "fecha_fin":      None,
            "inactivado_por": None,
            "creado_en":      datetime.utcnow(),
            "creado_por":     creado_por,
            "actualizado_en": None,
        }
        return str(_funcionarios().insert_one(doc).inserted_id)

    @staticmethod
    def listar(solo_activos: bool = True) -> list:
        filtro = {"activo": True} if solo_activos else {}
        return list(_funcionarios().find(filtro).sort([("cargo_categoria", 1), ("apellidos", 1)]))

    @staticmethod
    def obtener(funcionario_id: str):
        try:
            return _funcionarios().find_one({"_id": ObjectId(funcionario_id)})
        except Exception:
            return None

    @staticmethod
    def actualizar(funcionario_id: str, datos: dict):
        _funcionarios().update_one(
            {"_id": ObjectId(funcionario_id)},
            {"$set": {
                "nombres":         datos.get("nombres", "").strip(),
                "apellidos":       datos.get("apellidos", "").strip(),
                "cargo_id":        datos.get("cargo_id", "").strip(),
                "cargo_nombre":    datos.get("cargo_nombre", "").strip(),
                "cargo_categoria": datos.get("cargo_categoria", "").strip(),
                "telefono":        datos.get("telefono", "").strip(),
                "email":           datos.get("email", "").strip().lower(),
                "fecha_inicio":    datos.get("fecha_inicio", "").strip(),
                "horario":         _horario_desde(datos),
                "actualizado_en":  datetime.utcnow(),
            }}
        )

    @staticmethod
    def inactivar(funcionario_id: str, fecha_fin: str, inactivado_por: str):
        """RN-DIR-03: inactivación histórica, nunca eliminación."""
        _funcionarios().update_one(
            {"_id": ObjectId(funcionario_id)},
            {"$set": {
                "activo":         False,
                "fecha_fin":      fecha_fin,
                "inactivado_por": inactivado_por,
                "actualizado_en": datetime.utcnow(),
            }}
        )

    @staticmethod
    def reactivar(funcionario_id: str):
        _funcionarios().update_one(
            {"_id": ObjectId(funcionario_id)},
            {"$set": {
                "activo":         True,
                "fecha_fin":      None,
                "inactivado_por": None,
                "actualizado_en": datetime.utcnow(),
            }}
        )
