"""
app/configuracion/directorio/routes.py
Endpoints de administración del Directorio de Contactos.
Prefijo: /config/directorio

Usa ContactoModel/ContactoController del módulo de servicios.
El campo empresa_id llega como 'propiedad_id' en el payload.
Los teléfonos se envían como múltiples valores form y se
normalizan a [{numero, etiqueta}] antes de persistir.
"""

import base64
import logging
from io import BytesIO
from flask import Blueprint, request, session, send_file, abort
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.servicios.directorio.controller import ContactoController
from app.servicios.directorio.model import ContactoModel, BLOQUES_VALIDOS

logger = logging.getLogger(__name__)

directorio_cfg_bp = Blueprint("directorio_cfg", __name__, url_prefix="/config/directorio")


def _usuario():
    return session.get("num_doc") or session.get("usuario_id", "sistema")


def _parse_payload():
    """Extrae y normaliza el payload del request (JSON o multipart)."""
    import json as _json

    if request.is_json:
        datos = request.get_json(silent=True) or {}
        empresa_id = datos.get("propiedad_id") or datos.get("empresa_id", "")
        foto = None
        # telefonos puede ser lista de strings o lista de dicts
        tels = datos.get("telefonos", [])
    else:
        empresa_id = request.form.get("propiedad_id") or request.form.get("empresa_id", "")
        # getlist captura múltiples valores del mismo campo
        tels_raw = request.form.getlist("telefonos")
        # Si hay un solo valor que parece JSON, intentar parsearlo
        if len(tels_raw) == 1:
            try:
                parsed = _json.loads(tels_raw[0])
                if isinstance(parsed, list):
                    tels_raw = parsed
            except Exception:
                pass
        tels = tels_raw
        datos = request.form.to_dict()
        foto = request.files.get("foto")

    # Normalizar teléfonos → [{numero, prefijo, etiqueta}]
    tels_norm = []
    for t in tels:
        if isinstance(t, dict):
            num = (t.get("numero") or "").strip()
            if num:
                tels_norm.append({
                    "numero":   num,
                    "prefijo":  t.get("prefijo", "").strip(),
                    "etiqueta": t.get("etiqueta", "").strip(),
                })
        elif isinstance(t, str) and t.strip():
            tels_norm.append({"numero": t.strip(), "prefijo": "", "etiqueta": ""})

    datos["telefonos"] = tels_norm

    for flag in ("es_visible_para_residentes", "es_visible_para_seguridad",
                 "es_visible_para_administracion", "vinculado_al_boton_de_panico"):
        val = datos.get(flag, "")
        if isinstance(val, bool):
            continue
        datos[flag] = str(val).lower() in ("true", "1", "on")

    return empresa_id, datos, foto


def _serializar_contacto(doc: dict) -> dict:
    """Devuelve el documento serializable sin los bytes de la foto."""
    d = serializar(doc)
    d.pop("foto_data", None)
    d.pop("foto_mimetype", None)
    d["tiene_foto"] = bool(doc.get("foto_data"))
    # Normalizar teléfonos → [{numero, prefijo, etiqueta}]
    tels = doc.get("telefonos", [])
    d["telefonos"] = [
        {"numero": t["numero"], "prefijo": t.get("prefijo",""), "etiqueta": t.get("etiqueta","")}
        if isinstance(t, dict) else {"numero": t, "prefijo": "", "etiqueta": ""}
        for t in tels
        if (t.get("numero","") if isinstance(t, dict) else t)
    ]
    return d


# ── GET: países / prefijos ───────────────────────────────────────────────

@directorio_cfg_bp.route("/paises", methods=["GET"])
@requiere_superadmin
def listar_paises():
    from app import db
    try:
        paises = list(db["paises_prefijos"].find(
            {}, {"nombre_pais": 1, "prefijo": 1, "bandera": 1}
        ).sort("nombre_pais", 1))
        return ok(serializar(paises))
    except Exception as e:
        return err(str(e))


# ── GET: listar contactos ─────────────────────────────────────────────────

@directorio_cfg_bp.route("", methods=["GET"])
@requiere_superadmin
def listar():
    empresa_id = request.args.get("propiedad_id") or request.args.get("empresa_id", "")
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    bloque = (request.args.get("bloque") or "").upper().strip()
    try:
        docs = ContactoModel.listar_por_empresa(empresa_id, solo_activos=False)
    except Exception as e:
        logger.error("Error listando contactos empresa=%s: %s", empresa_id, e)
        return err("Error interno", 500)
    if bloque and bloque in BLOQUES_VALIDOS:
        docs = [d for d in docs if d.get("bloque") == bloque]
    return ok([_serializar_contacto(d) for d in docs])


# ── POST: crear contacto ──────────────────────────────────────────────────

@directorio_cfg_bp.route("", methods=["POST"])
@requiere_superadmin
def crear():
    empresa_id, datos, foto = _parse_payload()
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    exito, resultado = ContactoController.crear(datos, empresa_id, _usuario(), foto_file=foto)
    if not exito:
        return err(resultado)
    return ok(resultado, status=201)


# ── GET foto ─────────────────────────────────────────────────────────────

@directorio_cfg_bp.route("/<contacto_id>/foto", methods=["GET"])
@requiere_superadmin
def foto(contacto_id):
    empresa_id = request.args.get("propiedad_id") or request.args.get("empresa_id") or ""
    doc = ContactoModel.obtener(contacto_id, empresa_id if empresa_id else None)
    if not doc or not doc.get("foto_data"):
        abort(404)
    try:
        raw = base64.b64decode(doc["foto_data"])
        return send_file(BytesIO(raw), mimetype=doc.get("foto_mimetype", "image/jpeg"))
    except Exception:
        abort(500)


# ── PUT: actualizar contacto ──────────────────────────────────────────────

@directorio_cfg_bp.route("/<contacto_id>", methods=["PUT"])
@requiere_superadmin
def actualizar(contacto_id):
    empresa_id, datos, foto = _parse_payload()
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    exito, resultado = ContactoController.actualizar(contacto_id, empresa_id, datos, foto_file=foto)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


# ── DELETE: eliminar contacto ─────────────────────────────────────────────

@directorio_cfg_bp.route("/<contacto_id>", methods=["DELETE"])
@requiere_superadmin
def eliminar(contacto_id):
    empresa_id = request.args.get("propiedad_id") or request.args.get("empresa_id") or ""
    if not empresa_id:
        # Intenta obtener el contacto sin filtro de empresa
        doc = ContactoModel.obtener(contacto_id)
        if not doc:
            return err("Contacto no encontrado", 404)
        empresa_id = str(doc.get("empresa_id", ""))
    exito, resultado = ContactoController.eliminar(contacto_id, empresa_id)
    if not exito:
        return err(resultado, 404)
    return ok(mensaje=resultado)
