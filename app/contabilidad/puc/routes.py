"""
app/contabilidad/puc/routes.py
───────────────────────────────
Blueprint Flask para el Plan Único de Cuentas.
Prefijo: /cont
"""

import io
import csv
from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.contabilidad.puc.controller import PucController

puc_bp = Blueprint("cont_puc", __name__, url_prefix="/cont")


@puc_bp.route("/puc", methods=["GET"])
@requiere_superadmin
def listar():
    filtros = {}
    if request.args.get("tipo"):
        filtros["tipo"] = request.args.get("tipo")
    if request.args.get("activa") is not None and request.args.get("activa") != "":
        filtros["activa"] = request.args.get("activa") == "true"
    arbol = request.args.get("arbol", "0") == "1"
    if arbol:
        _, data = PucController.listar_arbol(filtros)
        return ok(data)
    _, lista = PucController.listar(filtros)
    return ok(serializar(lista))


@puc_bp.route("/puc", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or request.form.to_dict()
    # Convertir booleanos que vienen como string desde FormData
    for campo_bool in ("exige_tercero", "exige_centro_costos"):
        if campo_bool in datos and isinstance(datos[campo_bool], str):
            datos[campo_bool] = datos[campo_bool].lower() in ("true", "1", "on")
    ip = request.remote_addr or ""
    exito, resultado = PucController.crear(datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(resultado)


@puc_bp.route("/puc/<cuenta_id>", methods=["GET"])
@requiere_superadmin
def obtener(cuenta_id):
    from app.contabilidad.puc.model import PucModel
    cuenta = PucModel.obtener(cuenta_id)
    if not cuenta:
        return err("Cuenta no encontrada", 404)
    return ok(serializar(cuenta))


@puc_bp.route("/puc/<cuenta_id>", methods=["PUT"])
@requiere_superadmin
def actualizar(cuenta_id):
    datos = request.get_json(silent=True) or request.form.to_dict()
    for campo_bool in ("exige_tercero", "exige_centro_costos", "activa"):
        if campo_bool in datos and isinstance(datos[campo_bool], str):
            datos[campo_bool] = datos[campo_bool].lower() in ("true", "1", "on")
    ip = request.remote_addr or ""
    exito, resultado = PucController.actualizar(cuenta_id, datos, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@puc_bp.route("/puc/<cuenta_id>/estado", methods=["PATCH"])
@requiere_superadmin
def cambiar_estado(cuenta_id):
    datos = request.get_json(silent=True) or {}
    activa = bool(datos.get("activa", False))
    ip = request.remote_addr or ""
    exito, resultado = PucController.cambiar_estado(cuenta_id, activa, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@puc_bp.route("/puc/<cuenta_id>", methods=["DELETE"])
@requiere_superadmin
def eliminar(cuenta_id):
    ip = request.remote_addr or ""
    exito, resultado = PucController.eliminar(cuenta_id, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@puc_bp.route("/puc/plantilla/<perfil>", methods=["POST"])
@requiere_superadmin
def cargar_plantilla(perfil):
    """Carga una plantilla PUC predeterminada para el perfil dado."""
    ip = request.remote_addr or ""
    exito, resultado = PucController.cargar_plantilla(perfil, session.get("num_doc", ""), ip)
    if not exito:
        return err(resultado)
    return ok(resultado)


@puc_bp.route("/puc/importar", methods=["POST"])
@requiere_superadmin
def importar():
    """Importación masiva desde JSON body o archivo CSV."""
    ip = request.remote_addr or ""
    usuario_id = session.get("num_doc", "")

    # Caso 1: JSON directo
    if request.is_json:
        cuentas = request.get_json(silent=True) or []
        exito, resultado = PucController.importar(cuentas, usuario_id, ip)
        if not exito:
            return err(resultado)
        return ok(resultado)

    # Caso 2: archivo CSV
    archivo = request.files.get("archivo")
    if not archivo:
        return err("Se requiere un archivo CSV o un body JSON con la lista de cuentas")
    try:
        contenido = archivo.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(contenido))
        cuentas = []
        for fila in reader:
            cuentas.append({
                "codigo":              fila.get("codigo", "").strip(),
                "nombre":              fila.get("nombre", "").strip(),
                "naturaleza":          fila.get("naturaleza", "D").strip().upper(),
                "nivel":               int(fila.get("nivel", 1) or 1),
                "padre_id":            fila.get("padre_id", "").strip() or None,
                "tipo":                fila.get("tipo", "local").strip(),
                "exige_tercero":       str(fila.get("exige_tercero", "")).lower() in ("true", "1", "si", "sí"),
                "exige_centro_costos": str(fila.get("exige_centro_costos", "")).lower() in ("true", "1", "si", "sí"),
            })
        exito, resultado = PucController.importar(cuentas, usuario_id, ip)
        if not exito:
            return err(resultado)
        return ok(resultado)
    except Exception as e:
        return err(f"Error procesando el archivo: {str(e)}")


@puc_bp.route("/puc/niif", methods=["GET"])
@requiere_superadmin
def cuentas_niif():
    """Lista cuentas NIIF disponibles para el selector de mapeo."""
    _, lista = PucController.cuentas_niif()
    return ok(serializar(lista))
