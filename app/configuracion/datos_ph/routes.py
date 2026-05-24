"""
app/configuracion/datos_ph/routes.py
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.configuracion.datos_ph.controller import DatosGeneralesPHController
from app.configuracion.catalogos.model import CatalogoModel

datos_ph_bp = Blueprint("config_datos_ph", __name__, url_prefix="/config")


# ── Catálogos de apoyo ────────────────────────────────────────────────────

@datos_ph_bp.route("/datos_ph/responsabilidades_dian", methods=["GET"])
@requiere_superadmin
def responsabilidades():
    return ok(CatalogoModel.responsabilidades_dian())

@datos_ph_bp.route("/datos_ph/actividades_ciiu", methods=["GET"])
@requiere_superadmin
def ciiu():
    return ok(CatalogoModel.actividades_ciiu())

@datos_ph_bp.route("/datos_ph/estratos", methods=["GET"])
@requiere_superadmin
def estratos():
    return ok(CatalogoModel.estratos())

@datos_ph_bp.route("/datos_ph/estados_contrato", methods=["GET"])
@requiere_superadmin
def estados_contrato():
    return ok(CatalogoModel.estados_contrato())

@datos_ph_bp.route("/datos_ph/obligaciones_rut", methods=["GET"])
@requiere_superadmin
def obligaciones_rut():
    return ok(CatalogoModel.obligaciones_rut())

@datos_ph_bp.route("/datos_ph/tipo_identificador_fiscal", methods=["GET"])
@requiere_superadmin
def tipo_identificador_fiscal():
    return ok(CatalogoModel.tipo_identificador_fiscal())

@datos_ph_bp.route("/datos_ph/tipos_organizacion", methods=["GET"])
@requiere_superadmin
def tipos_organizacion():
    return ok(CatalogoModel.tipos_organizacion())

@datos_ph_bp.route("/datos_ph/tributos", methods=["GET"])
@requiere_superadmin
def tributos():
    return ok(CatalogoModel.tributos())

@datos_ph_bp.route("/datos_ph/codigos_postales", methods=["GET"])
@requiere_superadmin
def codigos_postales():
    departamento = request.args.get("departamento", "")
    ciudad       = request.args.get("ciudad", "")
    return ok(CatalogoModel.codigos_postales(departamento, ciudad))


# ── CRUD datos generales ──────────────────────────────────────────────────

# Rutas especiales PRIMERO (sin parámetros dinámicos)
@datos_ph_bp.route("/datos_generales_ph", methods=["GET"])
@requiere_superadmin
def listar():
    exito, lista = DatosGeneralesPHController.listar()
    if not exito: return err(lista)
    return ok(serializar(lista))


@datos_ph_bp.route("/datos_generales_ph/empresas_configuradas", methods=["GET"])
@requiere_superadmin
def empresas_configuradas():
    from app import db
    ids = db["datos_generales_ph"].distinct("empresa_id")
    return ok([str(eid) for eid in ids])


# Ruta única con parámetro dinámico — maneja GET, POST, PUT, DELETE
@datos_ph_bp.route("/datos_generales_ph/<id_param>", methods=["GET", "POST", "PUT", "DELETE"])
@requiere_superadmin
def crud(id_param):
    if request.method == "GET":
        exito, data = DatosGeneralesPHController.obtener(id_param)
        if not exito: return err(data, 404)
        return ok(serializar(data))

    elif request.method == "POST":
        datos = request.get_json(silent=True) or request.form.to_dict()
        exito, resultado = DatosGeneralesPHController.crear(id_param, datos, session["num_doc"])
        if not exito: return err(resultado)
        return ok(resultado)

    elif request.method == "PUT":
        datos = request.get_json(silent=True) or request.form.to_dict()
        exito, resultado = DatosGeneralesPHController.actualizar(id_param, datos)
        if not exito: return err(resultado)
        return ok(mensaje=resultado)

    elif request.method == "DELETE":
        exito, resultado = DatosGeneralesPHController.eliminar(id_param)
        if not exito: return err(resultado)
        return ok(mensaje=resultado)
