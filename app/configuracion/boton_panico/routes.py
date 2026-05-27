"""
app/configuracion/boton_panico/routes.py
Endpoints de administración del módulo Botón de Pánico.
Prefijo: /config/boton_panico
"""

from flask import Blueprint, request
from bson import ObjectId

from app import db
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.servicios.boton_panico.model import PanicEventModel

panico_cfg_bp = Blueprint("panico_cfg", __name__, url_prefix="/config/boton_panico")


def _empresa_id():
    return request.args.get("propiedad_id", "").strip()


@panico_cfg_bp.route("/contactos", methods=["GET"])
@requiere_superadmin
def listar_contactos_vinculados():
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    try:
        contactos = list(
            db["directorio_contactos"].find(
                {
                    "empresa_id":                   ObjectId(eid),
                    "activo":                       True,
                    "vinculado_al_boton_de_panico": True,
                },
                {"nombre": 1, "cargo_titulo": 1, "bloque": 1, "telefonos": 1,
                 "es_visible_para_seguridad": 1, "es_visible_para_administracion": 1},
            ).sort("nombre", 1)
        )
        return ok(serializar(contactos))
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/eventos", methods=["GET"])
@requiere_superadmin
def listar_eventos():
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    try:
        limite = int(request.args.get("limite", 20))
        eventos = PanicEventModel.listar_por_empresa(eid, limite=limite)
        return ok(serializar(eventos))
    except Exception as e:
        return err(str(e))


@panico_cfg_bp.route("/stats", methods=["GET"])
@requiere_superadmin
def stats():
    eid = _empresa_id()
    if not eid:
        return err("propiedad_id requerido", 400)
    try:
        total_contactos = db["directorio_contactos"].count_documents({
            "empresa_id":                   ObjectId(eid),
            "activo":                       True,
            "vinculado_al_boton_de_panico": True,
        })
        total_eventos = db["panic_events"].count_documents({
            "empresa_id": ObjectId(eid),
        })
        ultimo = db["panic_events"].find_one(
            {"empresa_id": ObjectId(eid)},
            {"activado_en": 1, "residente_id": 1},
            sort=[("activado_en", -1)],
        )
        return ok({
            "total_contactos": total_contactos,
            "total_eventos":   total_eventos,
            "ultimo_evento":   serializar(ultimo) if ultimo else None,
        })
    except Exception as e:
        return err(str(e))
