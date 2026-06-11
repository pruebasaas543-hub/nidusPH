"""
app/configuracion/directorio/routes.py
Endpoints de administración del Directorio de Contactos.
Prefijo: /config/directorio

Todo vive en directorio_contactos:
  tipo="config"   → 1 documento por empresa  (bloques + límites)
  tipo="contacto" → N documentos por empresa (contactos individuales)
"""

import base64
import logging
from io import BytesIO
from flask import Blueprint, request, session, send_file, abort
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.servicios.directorio.controller import ContactoController
from app.servicios.directorio.model import ContactoModel, DirectorioConfigModel

logger = logging.getLogger(__name__)

directorio_cfg_bp = Blueprint("directorio_cfg", __name__, url_prefix="/config/directorio")


def _usuario():
    return session.get("num_doc") or session.get("usuario_id", "sistema")


def _eid():
    return request.args.get("propiedad_id") or request.args.get("empresa_id", "")


def _parse_payload():
    """Extrae y normaliza el payload del request (JSON o multipart)."""
    import json as _json

    if request.is_json:
        datos = request.get_json(silent=True) or {}
        empresa_id = datos.get("propiedad_id") or datos.get("empresa_id", "")
        foto = None
        tels = datos.get("telefonos", [])
    else:
        empresa_id = request.form.get("propiedad_id") or request.form.get("empresa_id", "")
        tels_raw = request.form.getlist("telefonos")
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
                 "es_visible_para_administracion", "vinculado_al_boton_de_panico",
                 "tiene_parqueadero"):
        val = datos.get(flag, "")
        if isinstance(val, bool):
            continue
        datos[flag] = str(val).lower() in ("true", "1", "on")

    # vehiculos puede llegar como JSON string en multipart
    if isinstance(datos.get("vehiculos"), str):
        try:
            import json as _json2
            datos["vehiculos"] = _json2.loads(datos["vehiculos"])
        except Exception:
            datos["vehiculos"] = []
    if not isinstance(datos.get("vehiculos"), list):
        datos["vehiculos"] = []

    return empresa_id, datos, foto


def _serializar_contacto(doc: dict) -> dict:
    """Devuelve el documento serializable sin los bytes de la foto."""
    d = serializar(doc)
    d.pop("foto_data", None)
    d.pop("foto_mimetype", None)
    d.pop("tipo", None)
    d["tiene_foto"] = bool(doc.get("foto_data"))
    tels = doc.get("telefonos", [])
    d["telefonos"] = [
        {"numero": t["numero"], "prefijo": t.get("prefijo", ""), "etiqueta": t.get("etiqueta", "")}
        if isinstance(t, dict) else {"numero": t, "prefijo": "", "etiqueta": ""}
        for t in tels
        if (t.get("numero", "") if isinstance(t, dict) else t)
    ]
    return d


# ── Bloques ───────────────────────────────────────────────────────────────────

@directorio_cfg_bp.route("/bloques", methods=["GET"])
@requiere_superadmin
def listar_bloques():
    empresa_id   = _eid()
    solo_activos = request.args.get("solo_activos", "false").lower() != "false"
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    try:
        bloques = DirectorioConfigModel.listar_bloques(empresa_id, solo_activos=solo_activos)
        return ok(bloques)
    except Exception as e:
        return err(str(e))


@directorio_cfg_bp.route("/bloques", methods=["POST"])
@requiere_superadmin
def crear_bloque():
    empresa_id = _eid()
    datos      = request.get_json(silent=True) or {}
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    if not datos.get("codigo", "").strip():
        return err("El código del bloque es obligatorio", 400)
    if not datos.get("nombre", "").strip():
        return err("El nombre del bloque es obligatorio", 400)
    try:
        codigo = DirectorioConfigModel.crear_bloque(empresa_id, datos)
        return ok({"codigo": codigo}, status=201)
    except ValueError as e:
        return err(str(e), 400)
    except Exception as e:
        return err(str(e))


@directorio_cfg_bp.route("/bloques/<codigo>", methods=["DELETE"])
@requiere_superadmin
def eliminar_bloque(codigo):
    empresa_id = _eid()
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    eliminado = DirectorioConfigModel.eliminar_bloque(empresa_id, codigo.upper())
    if not eliminado:
        return err("No se puede eliminar: es un bloque predeterminado del sistema o no existe.", 400)
    return ok(mensaje="Bloque eliminado")


@directorio_cfg_bp.route("/bloques/<codigo>", methods=["PUT"])
@requiere_superadmin
def actualizar_bloque(codigo):
    empresa_id = _eid()
    datos = request.get_json(silent=True) or {}
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    if not datos.get("nombre", "").strip():
        return err("El nombre es obligatorio", 400)
    try:
        DirectorioConfigModel.actualizar_bloque(empresa_id, codigo.upper(), datos)
        return ok(mensaje="Bloque actualizado")
    except Exception as e:
        return err(str(e))


@directorio_cfg_bp.route("/bloques/<codigo>/activo", methods=["PATCH"])
@requiere_superadmin
def toggle_bloque(codigo):
    empresa_id = _eid()
    datos  = request.get_json(silent=True) or {}
    activo = bool(datos.get("activo", True))
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    if not activo:
        count = ContactoModel.contar_por_bloque(empresa_id, codigo.upper())
        if count > 0:
            return err(
                f"No se puede inhabilitar. Hay {count} contacto(s) activo(s) en este bloque.",
                400,
            )
    try:
        DirectorioConfigModel.toggle_bloque(empresa_id, codigo.upper(), activo)
        return ok(mensaje="Estado actualizado")
    except Exception as e:
        return err(str(e))


# ── GET: países / prefijos ────────────────────────────────────────────────────

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


# ── GET/PUT: límites por bloque ───────────────────────────────────────────────

@directorio_cfg_bp.route("/limites", methods=["GET"])
@requiere_superadmin
def obtener_limites():
    empresa_id = _eid()
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    try:
        return ok(DirectorioConfigModel.obtener_limites(empresa_id))
    except Exception as e:
        return err(str(e))


@directorio_cfg_bp.route("/limites", methods=["PUT"])
@requiere_superadmin
def guardar_limites():
    empresa_id = _eid()
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    datos = request.get_json(silent=True) or {}
    limites = datos.get("limites", {})
    if not isinstance(limites, dict):
        return err("limites debe ser un objeto {BLOQUE: max}", 400)
    try:
        DirectorioConfigModel.guardar_limites(empresa_id, limites)
        return ok(mensaje="Límites guardados")
    except Exception as e:
        return err(str(e))


# ── GET: listar contactos ─────────────────────────────────────────────────────

@directorio_cfg_bp.route("", methods=["GET"])
@requiere_superadmin
def listar():
    empresa_id = _eid()
    if not empresa_id:
        return err("Debe indicar propiedad_id", 400)
    bloque = (request.args.get("bloque") or "").upper().strip()
    try:
        docs = ContactoModel.listar_por_empresa(empresa_id, solo_activos=False)
    except Exception as e:
        logger.error("Error listando contactos empresa=%s: %s", empresa_id, e)
        return err("Error interno", 500)
    if bloque:
        docs = [d for d in docs if d.get("bloque") == bloque]
    return ok([_serializar_contacto(d) for d in docs])


# ── POST: crear contacto ──────────────────────────────────────────────────────

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


# ── GET foto ──────────────────────────────────────────────────────────────────

@directorio_cfg_bp.route("/<contacto_id>/foto", methods=["GET"])
@requiere_superadmin
def foto(contacto_id):
    empresa_id = _eid()
    doc = ContactoModel.obtener(contacto_id, empresa_id if empresa_id else None)
    if not doc or not doc.get("foto_data"):
        abort(404)
    try:
        raw = base64.b64decode(doc["foto_data"])
        return send_file(BytesIO(raw), mimetype=doc.get("foto_mimetype", "image/jpeg"))
    except Exception:
        abort(500)


# ── PUT: actualizar contacto ──────────────────────────────────────────────────

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


# ── DELETE: eliminar contacto ─────────────────────────────────────────────────

@directorio_cfg_bp.route("/<contacto_id>", methods=["DELETE"])
@requiere_superadmin
def eliminar(contacto_id):
    empresa_id = _eid()
    if not empresa_id:
        doc = ContactoModel.obtener(contacto_id)
        if not doc:
            return err("Contacto no encontrado", 404)
        empresa_id = str(doc.get("empresa_id", ""))
    exito, resultado = ContactoController.eliminar(contacto_id, empresa_id)
    if not exito:
        return err(resultado, 404)
    return ok(mensaje=resultado)
