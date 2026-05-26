"""
app/configuracion/directorio/routes.py
Prefijo: /config/directorio
"""

import base64
from io import BytesIO
from flask import Blueprint, request, session, send_file
from app.configuracion.utils import requiere_superadmin, ok, err
from app.configuracion.directorio.controller import DirectorioController

directorio_cfg_bp = Blueprint("config_directorio", __name__, url_prefix="/config")


@directorio_cfg_bp.route("/directorio", methods=["GET"])
@requiere_superadmin
def listar():
    propiedad_id = request.args.get("propiedad_id", "").strip()
    bloque       = request.args.get("bloque", "").strip() or None
    exito, resultado = DirectorioController.listar(propiedad_id, bloque)
    if not exito:
        return err(resultado)
    return ok(resultado)


@directorio_cfg_bp.route("/directorio", methods=["POST"])
@requiere_superadmin
def crear():
    propiedad_id = request.form.get("propiedad_id", "").strip()
    telefonos    = request.form.getlist("telefonos")
    datos = {
        "bloque":                       request.form.get("bloque", ""),
        "nombre":                       request.form.get("nombre", ""),
        "telefonos":                    telefonos,
        "correo":                       request.form.get("correo", ""),
        "nota_referencia":              request.form.get("nota_referencia", ""),
        "es_visible_para_residentes":   request.form.get("es_visible_para_residentes") == "true",
        "requiere_autenticacion":       request.form.get("requiere_autenticacion") == "true",
        "permite_llamada_rapida":       request.form.get("permite_llamada_rapida") == "true",
        "vinculado_al_boton_de_panico": request.form.get("vinculado_al_boton_de_panico") == "true",
    }
    archivo = request.files.get("foto")
    exito, resultado = DirectorioController.crear(
        propiedad_id, datos, archivo, session.get("num_doc", "")
    )
    if not exito:
        return err(resultado)
    return ok(resultado)


@directorio_cfg_bp.route("/directorio/<contacto_id>", methods=["PUT"])
@requiere_superadmin
def actualizar(contacto_id):
    telefonos = request.form.getlist("telefonos")
    datos = {
        "bloque":                       request.form.get("bloque", ""),
        "nombre":                       request.form.get("nombre", ""),
        "telefonos":                    telefonos,
        "correo":                       request.form.get("correo", ""),
        "nota_referencia":              request.form.get("nota_referencia", ""),
        "es_visible_para_residentes":   request.form.get("es_visible_para_residentes") == "true",
        "requiere_autenticacion":       request.form.get("requiere_autenticacion") == "true",
        "permite_llamada_rapida":       request.form.get("permite_llamada_rapida") == "true",
        "vinculado_al_boton_de_panico": request.form.get("vinculado_al_boton_de_panico") == "true",
    }
    archivo = request.files.get("foto")
    exito, resultado = DirectorioController.actualizar(contacto_id, datos, archivo)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@directorio_cfg_bp.route("/directorio/<contacto_id>", methods=["DELETE"])
@requiere_superadmin
def eliminar(contacto_id):
    exito, resultado = DirectorioController.eliminar(contacto_id)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@directorio_cfg_bp.route("/directorio/<contacto_id>/foto", methods=["GET"])
def foto(contacto_id):
    exito, resultado = DirectorioController.obtener_foto(contacto_id)
    if not exito:
        from flask import abort
        abort(404)
    try:
        raw = base64.b64decode(resultado["data"])
        return send_file(BytesIO(raw), mimetype=resultado["mimetype"])
    except Exception:
        from flask import abort
        abort(500)
