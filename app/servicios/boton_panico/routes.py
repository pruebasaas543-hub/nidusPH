"""
app/servicios/boton_panico/routes.py
API REST del módulo Botón de Pánico.
Prefijo: /servicios/boton_panico
"""

from flask import Blueprint, request, session
from bson import ObjectId

from app import db
from app.configuracion.utils import requiere_login, ok, err, serializar
from app.servicios.boton_panico.controller import PanicController
from app.servicios.boton_panico.model import PanicEventModel

panico_bp = Blueprint("boton_panico", __name__, url_prefix="/servicios/boton_panico")


def _usuario():        return session.get("num_doc") or session.get("usuario_id", "sistema")
def _empresa_id():     return session.get("empresa_id", "")
def _nombre_res():     return session.get("nombres") or _usuario()
def _nombre_empresa(): return session.get("empresa_nombre") or "la propiedad"


# ── Países / prefijos ─────────────────────────────────────────────────────

@panico_bp.route("/paises", methods=["GET"])
@requiere_login
def listar_paises():
    try:
        paises = list(db["paises_prefijos"].find(
            {}, {"nombre_pais": 1, "prefijo": 1, "bandera": 1, "longitud_celular_estandar": 1}
        ).sort("nombre_pais", 1))
        return ok(serializar(paises))
    except Exception as e:
        return err(str(e))


# ── Configuración del residente ───────────────────────────────────────────

@panico_bp.route("/config", methods=["GET"])
@requiere_login
def obtener_config():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    _, cfg = PanicController.obtener_config(eid, _usuario())
    return ok(serializar(cfg))


@panico_bp.route("/config", methods=["PUT"])
@requiere_login
def guardar_config():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    datos = request.get_json(silent=True) or {}
    exito, resultado = PanicController.guardar_config(eid, _usuario(), datos)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


# ── Contactos del directorio habilitados para pánico ─────────────────────

@panico_bp.route("/directorio", methods=["GET"])
@requiere_login
def directorio_panico():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    try:
        contactos = list(
            db["directorio_contactos"].find(
                {
                    "empresa_id":                   ObjectId(eid),
                    "activo":                       True,
                    "vinculado_al_boton_de_panico": True,
                },
                {"nombre": 1, "cargo_titulo": 1, "bloque": 1, "telefonos": 1},
            ).sort("nombre", 1)
        )
        return ok(serializar(contactos))
    except Exception as e:
        return err(str(e))


# ── Activar pánico ────────────────────────────────────────────────────────

@panico_bp.route("/trigger", methods=["POST"])
@requiere_login
def trigger():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    exito, resultado = PanicController.trigger(
        eid, _usuario(), _nombre_res(), _nombre_empresa(),
        request.remote_addr or "",
    )
    if not exito:
        return err(resultado)
    return ok(serializar(resultado))


# ── Historial de activaciones ─────────────────────────────────────────────

@panico_bp.route("/eventos", methods=["GET"])
@requiere_login
def listar_eventos():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    eventos = PanicEventModel.listar_por_residente(eid, _usuario(), limite=5)
    return ok(serializar(eventos))
