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
                     "es_visible_para_administracion", "vinculado_al_boton_de_panico"):
            datos[flag] = datos.get(flag, "").lower() in ("true", "1", "on")
        foto = request.files.get("foto")
    return datos, foto


_BLOQUE_MAP = {"ADMIN": "ADMINISTRACION", "LOGISTICA": "LOGISTICA"}


@directorio_bp.route("/bloques", methods=["GET"])
@requiere_login
def listar_bloques_usuario():
    """Devuelve los bloques activos de la empresa en sesión (para usuarios de copropiedad)."""
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    try:
        from app.servicios.directorio.model import DirectorioConfigModel
        bloques = DirectorioConfigModel.listar_bloques(eid, solo_activos=True)
        return ok(bloques)
    except Exception as e:
        return err(str(e))


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
    campo_vis = None
    if not session.get("es_sistema"):
        from app.servicios.permisos.model import PermisosRolModel
        campo_vis = PermisosRolModel.campo_visibilidad(session.get("rol", ""))
    exito, lista = ContactoController.listar(eid, solo_activos, campo_vis)
    if not exito:
        return err(lista)
    resultado = []
    for doc in lista:
        d = serializar(doc)
        d["tiene_foto"] = bool(doc.get("foto_data"))
        d.pop("foto_data", None)
        d.pop("foto_mimetype", None)
        resultado.append(d)
    return ok(resultado)


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


@directorio_bp.route("/residentes/plantilla", methods=["GET"])
@requiere_login
def plantilla_residentes():
    """Descarga un CSV de ejemplo para importación masiva de residentes."""
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Nombres", "Apellidos", "Tipo de residente", "Torre", "Apartamento",
                     "Telefono", "Parqueadero", "Placa", "Color vehiculo", "Marca vehiculo",
                     "Visible para residentes", "Visible para seguridad", "Visible para administracion"])
    writer.writerow(["Juan Carlos", "García Martínez", "Propietario", "A", "101", "3112345678",
                     "Sí", "ABC123", "Blanco", "Chevrolet Spark", "Sí", "No", "No"])
    writer.writerow(["María Fernanda", "López Ruiz", "Arrendatario", "B", "205", "3209876543",
                     "No", "", "", "", "Sí", "No", "Sí"])
    output.seek(0)
    from flask import Response
    return Response(
        output.getvalue().encode("utf-8-sig"),  # utf-8-sig para que Excel lo abra bien
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=plantilla_residentes.csv"}
    )


@directorio_bp.route("/residentes/importar", methods=["POST"])
@requiere_login
def importar_residentes():
    """Importación masiva de residentes desde CSV o Excel."""
    eid = _empresa_id()
    if not eid:
        return err("No hay empresa en sesión", 400)
    if "archivo" not in request.files:
        return err("Campo 'archivo' requerido", 400)
    archivo = request.files["archivo"]
    nombre_archivo = archivo.filename.lower()

    filas = []
    try:
        if nombre_archivo.endswith(".xlsx") or nombre_archivo.endswith(".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return err("El archivo Excel está vacío", 400)
            headers = [str(h or "").strip().lower() for h in rows[0]]
            for row in rows[1:]:
                filas.append({headers[i]: str(v or "").strip() for i, v in enumerate(row) if i < len(headers)})
        elif nombre_archivo.endswith(".csv"):
            import csv, io
            content = archivo.read().decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                filas.append({k.strip().lower(): (v or "").strip() for k, v in row.items()})
        else:
            return err("Formato no soportado. Usa CSV o XLSX.", 400)
    except Exception as e:
        return err(f"Error al leer el archivo: {e}", 400)

    if not filas:
        return err("El archivo no contiene datos", 400)

    def _bool_col(row, *keys):
        for k in keys:
            v = (row.get(k) or "").lower()
            if v in ("sí", "si", "s", "yes", "1", "true", "x"):
                return True
            if v in ("no", "n", "0", "false"):
                return False
        return True  # default visible

    from app.servicios.directorio.controller import ContactoController
    from datetime import datetime as _dt
    from bson import ObjectId as _ObjId

    creados, errores = 0, []
    for i, fila in enumerate(filas, start=2):
        nombres    = fila.get("nombres") or fila.get("nombre") or ""
        apellidos  = fila.get("apellidos") or fila.get("apellido") or ""
        tipo       = fila.get("tipo de residente") or fila.get("tipo_residente") or fila.get("tipo") or "Propietario"
        torre      = fila.get("torre") or fila.get("bloque") or ""
        apartamento= fila.get("apartamento") or fila.get("apto") or ""
        telefono   = fila.get("telefono") or fila.get("teléfono") or fila.get("tel") or ""

        if not nombres:
            errores.append(f"Fila {i}: 'Nombres' vacío, omitida.")
            continue
        if tipo not in ("Propietario", "Arrendatario"):
            tipo = "Propietario" if "prop" in tipo.lower() else "Arrendatario"

        vis_res  = _bool_col(fila, "visible para residentes", "visible_residentes")
        vis_seg  = _bool_col(fila, "visible para seguridad",  "visible_seguridad")
        vis_adm  = _bool_col(fila, "visible para administracion", "visible para administración", "visible_admin")

        parqueadero = _bool_col(fila, "parqueadero", "tiene_parqueadero")
        placa  = (fila.get("placa") or "").strip().upper()
        color  = (fila.get("color vehiculo") or fila.get("color") or "").strip()
        marca  = (fila.get("marca vehiculo") or fila.get("marca") or "").strip()
        vehiculo = {"placa": placa, "color": color, "marca": marca} if (parqueadero and placa) else {}

        datos = {
            "bloque":      "RESIDENTES",
            "nombre":      nombres,
            "apellidos":   apellidos,
            "tipo_residente": tipo,
            "torre":       torre,
            "apartamento": apartamento,
            "tiene_parqueadero": parqueadero,
            "vehiculo":    vehiculo,
            "telefonos":   [{"numero": telefono, "prefijo": "+57"}] if telefono else [],
            "cargo_titulo": "",
            "correo":      "",
            "es_visible_para_residentes":    vis_res,
            "es_visible_para_seguridad":     vis_seg,
            "es_visible_para_administracion": vis_adm,
            "vinculado_al_boton_de_panico":  False,
        }
        exito, res = ContactoController.crear(datos, eid, _usuario())
        if exito:
            creados += 1
        else:
            errores.append(f"Fila {i}: {res}")

    return ok({
        "creados": creados,
        "errores": errores,
        "mensaje": f"{creados} residente(s) importado(s) correctamente." + (f" {len(errores)} omitido(s)." if errores else "")
    }, status=201)


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
