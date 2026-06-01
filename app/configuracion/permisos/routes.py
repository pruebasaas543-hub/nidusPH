"""
app/configuracion/permisos/routes.py
Endpoints de administración de permisos por rol y módulo.
Prefijo: /config/permisos

Solo accesible por superadmin.
"""

from flask import Blueprint, request
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.servicios.permisos.model import PermisosRolModel, MODULOS_DISPONIBLES
from app import db
from bson import ObjectId

permisos_cfg_bp = Blueprint("permisos_cfg", __name__, url_prefix="/config/permisos")


def _eid():
    return request.args.get("propiedad_id") or request.args.get("empresa_id", "")


@permisos_cfg_bp.route("/roles", methods=["GET"])
@requiere_superadmin
def listar_roles():
    """Retorna los roles disponibles (no sistema) para asignar permisos."""
    empresa_id = _eid()
    try:
        # Roles custom (no de sistema) — son los que aplican en copropiedad
        roles = list(db["roles"].find(
            {"es_sistema": {"$ne": True}},
            {"nombre": 1, "descripcion": 1}
        ).sort("nombre", 1))
        return ok(serializar(roles))
    except Exception as e:
        return err(str(e))


@permisos_cfg_bp.route("", methods=["GET"])
@requiere_superadmin
def obtener_permisos():
    """
    Retorna los permisos configurados para una empresa.
    Responde un objeto:
    {
      "<rol_id>": {
        "rol_nombre": "...",
        "modulos": {
          "directorio": { "ver": true, "crear": false, ... }
        }
      }
    }
    """
    empresa_id = _eid()
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    try:
        roles = list(db["roles"].find(
            {"es_sistema": {"$ne": True}},
            {"nombre": 1}
        ))
        resultado = {}
        for rol in roles:
            rid = str(rol["_id"])
            resultado[rid] = {
                "rol_nombre": rol["nombre"],
                "modulos": {
                    modulo: PermisosRolModel.obtener(empresa_id, rid, modulo)
                    for modulo in MODULOS_DISPONIBLES
                },
            }
        return ok(resultado)
    except Exception as e:
        return err(str(e))


@permisos_cfg_bp.route("", methods=["PUT"])
@requiere_superadmin
def guardar_permisos():
    """
    Guarda los permisos de un rol para un módulo específico.
    Body: { "rol_id": "...", "modulo": "directorio", "acciones": { "ver": true, ... } }
    """
    empresa_id = _eid()
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    datos = request.get_json(silent=True) or {}
    rol_id  = datos.get("rol_id", "").strip()
    modulo  = datos.get("modulo", "").strip()
    acciones = datos.get("acciones", {})
    if not rol_id:
        return err("Debe indicar rol_id", 400)
    if modulo not in MODULOS_DISPONIBLES:
        return err(f"Módulo inválido. Opciones: {', '.join(MODULOS_DISPONIBLES)}", 400)
    if not isinstance(acciones, dict):
        return err("acciones debe ser un objeto", 400)
    try:
        PermisosRolModel.guardar(empresa_id, rol_id, modulo, acciones)
        return ok(mensaje="Permisos guardados")
    except Exception as e:
        return err(str(e))
