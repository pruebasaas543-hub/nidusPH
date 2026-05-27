"""
app/servicios/directorio/routes.py
API REST del módulo Directorio de Contactos.
Prefijo: /servicios/directorio
"""

import base64
from flask import Blueprint, request, session, send_file, abort
from io import BytesIO
from app.configuracion.utils import requiere_login, ok, err, serializar
from app.servicios.directorio.controller import ContactoController
from app import db

directorio_bp = Blueprint("directorio", __name__, url_prefix="/servicios/directorio")


def _usuario():
    return session.get("num_doc") or session.get("usuario_id", "sistema")

def _empresa_id():
    return session.get("empresa_id", "")


def _parse_contacto_payload():
    import json as _json
    if request.is_json:
        datos = request.get_json(silent=True) or {}
        foto  = None
    else:
        raw   = request.form.to_dict()
        datos = dict(raw)
        tel_raw = datos.get("telefonos", "[]")
        if isinstance(tel_raw, str):
            try:   datos["telefonos"] = _json.loads(tel_raw)
            except: datos["telefonos"] = []
        for flag in ("es_visible_para_residentes", "es_visible_para_seguridad",
                     "es_visible_para_administracion", "vinculado_al_boton_de_panico", "activo"):
            datos[flag] = datos.get(flag, "").lower() in ("true", "1", "on")
        foto = request.files.get("foto")
    return datos, foto


_BLOQUE_MAP = {"ADMIN": "ADMINISTRACION", "LOGISTICA": "LOGISTICA"}


@directorio_bp.route("/paises", methods=["GET"])
@requiere_login
def listar_paises():
    try:
        paises = list(db["paises_prefijos"].find(
            {}, {"nombre_pais": 1, "prefijo": 1, "bandera": 1, "longitud_celular_estandar": 1}
        ).sort("nombre_pais", 1))
        return ok(serializar(paises))
    except Exception as e:
        return err(str(e))


@directorio_bp.route("/cargos", methods=["GET"])
@requiere_login
def listar_cargos():
    bloque = request.args.get("bloque", "").upper().strip()
    bloque_col = _BLOQUE_MAP.get(bloque)
    if not bloque_col:
        return ok([])
    try:
        docs = list(db["cargofuncionarios"].find(
            {"bloque_directorio_defecto": bloque_col},
            {"nombre_cargo": 1}
        ).sort("nombre_cargo", 1))
        return ok([{"_id": str(d["_id"]), "nombre": d["nombre_cargo"]} for d in docs])
    except Exception as e:
        return err(str(e))


@directorio_bp.route("/contactos", methods=["GET"])
@requiere_login
def listar_contactos():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    solo_activos = request.args.get("solo_activos", "1") == "1"
    exito, lista = ContactoController.listar(eid, solo_activos)
    if not exito:
        return err(lista)
    return ok(serializar(lista))


@directorio_bp.route("/contactos", methods=["POST"])
@requiere_login
def crear_contacto():
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    datos, foto = _parse_contacto_payload()
    exito, resultado = ContactoController.crear(datos, eid, _usuario(), foto_file=foto)
    if not exito:
        return err(resultado)
    return ok(resultado, status=201)


@directorio_bp.route("/contactos/<contacto_id>", methods=["GET"])
@requiere_login
def obtener_contacto(contacto_id):
    eid = _empresa_id()
    exito, data = ContactoController.obtener(contacto_id, eid)
    if not exito:
        return err(data, 404)
    doc = serializar(data)
    doc.pop("foto_data", None)
    doc.pop("foto_mimetype", None)
    doc["tiene_foto"] = bool(data.get("foto_data"))
    return ok(doc)


@directorio_bp.route("/contactos/<contacto_id>", methods=["PUT"])
@requiere_login
def actualizar_contacto(contacto_id):
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    datos, foto = _parse_contacto_payload()
    exito, resultado = ContactoController.actualizar(contacto_id, eid, datos, foto_file=foto)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@directorio_bp.route("/contactos/<contacto_id>", methods=["DELETE"])
@requiere_login
def eliminar_contacto(contacto_id):
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    exito, resultado = ContactoController.eliminar(contacto_id, eid)
    if not exito:
        return err(resultado, 404)
    return ok(mensaje=resultado)


@directorio_bp.route("/contactos/<contacto_id>/foto", methods=["GET"])
@requiere_login
def foto_contacto(contacto_id):
    eid = _empresa_id()
    exito, data = ContactoController.obtener(contacto_id, eid)
    if not exito or not data.get("foto_data"):
        abort(404)
    try:
        raw      = base64.b64decode(data["foto_data"])
        mimetype = data.get("foto_mimetype", "image/jpeg")
        return send_file(BytesIO(raw), mimetype=mimetype)
    except Exception:
        abort(500)
