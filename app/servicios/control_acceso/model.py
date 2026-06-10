"""
app/servicios/control_acceso/model.py
─────────────────────────────────────
Modelos del módulo Control de Acceso. Aislado del resto.

Colecciones NUEVAS (no tocan las existentes):
  - access_credentials : QR / PIN / recurrentes para visitantes
  - access_logs        : bitácora de ingresos en portería

Reutiliza colecciones existentes SOLO en lectura/aditivo:
  - users        : se agrega el campo `pin_coaccion` (bytes bcrypt) sin tocar `password`
  - empresas     : conjunto residencial (conjunto_id == empresa_id)
  - asociaciones : unidad del residente (torre/apartamento)
"""

import secrets
import string
from datetime import datetime, timezone, timedelta

import bcrypt
from bson import ObjectId

from app import db


# ── Zona horaria Colombia (sin dependencias externas) ──────────────────────
TZ_BOGOTA = timezone(timedelta(hours=-5))


def _credentials(): return db["access_credentials"]
def _logs():        return db["access_logs"]
def _users():       return db["users"]


def _ahora_bogota() -> datetime:
    return datetime.now(TZ_BOGOTA)


def generar_codigo(longitud: int = 6) -> str:
    """Código alfanumérico de 6 caracteres (sin caracteres ambiguos)."""
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin O,0,I,1,L
    return "".join(secrets.choice(alfabeto) for _ in range(longitud))


class AccessCredentialModel:
    """Credenciales de acceso (QR / PIN / recurrentes / proveedores)."""

    @staticmethod
    def crear(conjunto_id: str, solicitante_id: str, visitante: dict,
              tipo_credencial: str = "unico", metodo: str = "QR",
              configuracion_recurrencia: dict = None,
              vigencia_inicio: datetime = None, vigencia_fin: datetime = None,
              unidad: dict = None) -> dict:
        """Crea una credencial. Devuelve el doc con su `codigo` (6 chars)."""
        codigo = generar_codigo()
        # Garantizar unicidad del código dentro del conjunto
        while _credentials().find_one({"conjunto_id": ObjectId(conjunto_id),
                                       "codigo": codigo, "estado": "activo"}):
            codigo = generar_codigo()

        doc = {
            "conjunto_id":     ObjectId(conjunto_id),
            "solicitante_id":  ObjectId(solicitante_id) if solicitante_id else None,
            "unidad":          unidad or {},          # {torre, apartamento, bloque}
            "visitante":       visitante or {},        # {nombre, documento, tipo_documento, vehiculo}
            "tipo_credencial": tipo_credencial,        # unico | recurrente | proveedor
            "metodo_autenticacion": metodo,            # QR | PIN
            "codigo":          codigo,                 # 6 chars (sirve para QR y PIN manual)
            "configuracion_recurrencia": configuracion_recurrencia or {},
            "vigencia": {
                "inicio": vigencia_inicio or _ahora_bogota(),
                "fin":    vigencia_fin,
            },
            "estado":     "activo",
            "creado_en":  datetime.utcnow(),
        }
        res = _credentials().insert_one(doc)
        doc["_id"] = res.inserted_id
        return doc

    @staticmethod
    def buscar_por_codigo(conjunto_id: str, codigo: str) -> dict:
        """Busca una credencial activa por su código dentro del conjunto."""
        return _credentials().find_one({
            "conjunto_id": ObjectId(conjunto_id),
            "codigo":      (codigo or "").strip().upper(),
            "estado":      "activo",
        })

    @staticmethod
    def listar_por_solicitante(conjunto_id: str, solicitante_id: str) -> list:
        return list(_credentials().find({
            "conjunto_id":    ObjectId(conjunto_id),
            "solicitante_id": ObjectId(solicitante_id),
        }).sort("creado_en", -1))

    @staticmethod
    def listar_por_conjunto(conjunto_id: str) -> list:
        """Todas las credenciales del conjunto (para el SuperAdmin)."""
        return list(_credentials().find({
            "conjunto_id": ObjectId(conjunto_id),
        }).sort("creado_en", -1))

    @staticmethod
    def revocar(credencial_id: str) -> bool:
        r = _credentials().update_one(
            {"_id": ObjectId(credencial_id)},
            {"$set": {"estado": "revocado", "actualizado_en": datetime.utcnow()}},
        )
        return r.modified_count > 0

    # ── Validaciones de negocio (vigencia y ventana de tiempo) ─────────────
    @staticmethod
    def vigencia_ok(cred: dict, ahora: datetime = None) -> bool:
        ahora = ahora or _ahora_bogota()
        vig = cred.get("vigencia", {})
        ini, fin = vig.get("inicio"), vig.get("fin")
        if ini and _aware(ini) > ahora:
            return False
        if fin and _aware(fin) < ahora:
            return False
        return True

    @staticmethod
    def ventana_tiempo_ok(cred: dict, ahora: datetime = None) -> bool:
        """Para recurrentes: valida día permitido y rango horario (hora Bogotá).

        dias_permitidos: lista de enteros (lunes=1 … domingo=7).
        """
        if cred.get("tipo_credencial") != "recurrente":
            return True  # únicos/proveedores no tienen ventana
        ahora = ahora or _ahora_bogota()
        conf = cred.get("configuracion_recurrencia", {}) or {}
        dias = conf.get("dias_permitidos") or []
        # Python: Monday=0 → convertimos a 1..7
        dia_actual = ahora.isoweekday()  # 1=lunes … 7=domingo
        if dias and dia_actual not in dias:
            return False
        h_ini, h_fin = conf.get("hora_inicio"), conf.get("hora_fin")
        if h_ini and h_fin:
            hhmm = ahora.strftime("%H:%M")
            if not (h_ini <= hhmm <= h_fin):
                return False
        return True


def _aware(dt: datetime) -> datetime:
    """Normaliza un datetime a aware (asume Bogotá si viene naive)."""
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=TZ_BOGOTA)
    return dt


class AccessLogModel:
    """Bitácora de ingresos en portería (minuta digital)."""

    @staticmethod
    def registrar(conjunto_id: str, *, visitante: dict = None, unidad: dict = None,
                  metodo: str = "", estado: str = "registrado",
                  coaccion_activa: bool = False, credencial_id=None,
                  vigilante_id: str = "", detalle: str = "") -> str:
        doc = {
            "conjunto_id":    ObjectId(conjunto_id),
            "visitante":      visitante or {},
            "unidad":         unidad or {},
            "metodo":         metodo,            # QR | PIN | CEDULA | MANUAL | CITOFONIA
            "estado":         estado,            # registrado | autorizado | rechazado | ingreso_manual | autorizado_citofonia | coaccion
            "coaccion_activa": bool(coaccion_activa),
            "credencial_id":  ObjectId(credencial_id) if credencial_id else None,
            "vigilante_id":   vigilante_id,
            "detalle":        detalle,
            "creado_en":      datetime.utcnow(),
        }
        return str(_logs().insert_one(doc).inserted_id)

    @staticmethod
    def actualizar_estado(log_id: str, estado: str, detalle: str = "") -> bool:
        upd = {"estado": estado, "actualizado_en": datetime.utcnow()}
        if detalle:
            upd["detalle"] = detalle
        r = _logs().update_one({"_id": ObjectId(log_id)}, {"$set": upd})
        return r.modified_count > 0

    @staticmethod
    def obtener(log_id: str) -> dict:
        try:
            return _logs().find_one({"_id": ObjectId(log_id)}) or {}
        except Exception:
            return {}

    @staticmethod
    def listar(conjunto_id: str, limite: int = 50) -> list:
        return list(_logs().find({"conjunto_id": ObjectId(conjunto_id)})
                    .sort("creado_en", -1).limit(limite))

    @staticmethod
    def coacciones_activas(conjunto_id: str, minutos: int = 30) -> list:
        """Coacciones recientes (para el panel de monitoreo por polling)."""
        desde = datetime.utcnow() - timedelta(minutes=minutos)
        return list(_logs().find({
            "conjunto_id":     ObjectId(conjunto_id),
            "coaccion_activa": True,
            "creado_en":       {"$gte": desde},
        }).sort("creado_en", -1))


class CoaccionModel:
    """PIN de coacción del residente — mismo hashing (bcrypt) que `password`."""

    @staticmethod
    def set_pin(user_id: str, pin: str) -> bool:
        hashed = bcrypt.hashpw(str(pin).encode("utf-8"), bcrypt.gensalt())
        r = _users().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"pin_coaccion": hashed, "pin_coaccion_actualizado": datetime.utcnow()}},
        )
        return r.modified_count > 0

    @staticmethod
    def verificar_pin(user_id: str, pin: str) -> bool:
        u = _users().find_one({"_id": ObjectId(user_id)}, {"pin_coaccion": 1})
        h = (u or {}).get("pin_coaccion")
        if not h:
            return False
        try:
            return bcrypt.checkpw(str(pin).encode("utf-8"), h)
        except Exception:
            return False

    @staticmethod
    def buscar_por_pin(conjunto_id: str, pin: str) -> dict:
        """Busca, entre los residentes del conjunto, alguno cuyo PIN de coacción
        coincida. Devuelve {user, asociacion} o {} si ninguno."""
        # Usuarios asociados al conjunto
        asocs = list(db["asociaciones"].find({
            "empresa_id": ObjectId(conjunto_id), "activo": True,
        }))
        for a in asocs:
            uid = a.get("user_id")
            if not uid:
                continue
            if CoaccionModel.verificar_pin(str(uid), pin):
                u = _users().find_one({"_id": uid}, {"password": 0, "pin_coaccion": 0})
                return {"user": u, "asociacion": a}
        return {}
