"""
app/configuracion/planes/routes.py
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.configuracion.planes.controller import PlanController

planes_bp = Blueprint("config_planes", __name__, url_prefix="/config")


@planes_bp.route("/estado_planes", methods=["GET"])
@requiere_superadmin
def estado_planes():
    from app import db
    col = db["estado_planes"]
    docs = list(col.find({}, {"nombre": 1}).sort("nombre", 1))
    if not docs:
        # Sembrar estados por defecto la primera vez
        col.insert_many([
            {"nombre": "activo"},
            {"nombre": "archivado"},
        ])
        docs = list(col.find({}, {"nombre": 1}).sort("nombre", 1))
    return ok(serializar(docs))


@planes_bp.route("/tipo_moneda", methods=["GET"])
@requiere_superadmin
def tipo_moneda():
    from app import db
    docs = list(db["tipo_moneda"].find(
        {}, {"pais_uso": 1, "abreviatura": 1, "nombre": 1}
    ).sort("pais_uso", 1))
    return ok(serializar(docs))


@planes_bp.route("/canales_soporte", methods=["GET"])
@requiere_superadmin
def canales_soporte():
    from app import db
    col = db["canales_soporte"]
    docs = list(col.find({}, {"id_canal": 1, "nombre": 1}).sort("nombre", 1))
    if not docs:
        # Sembrar canales por defecto la primera vez
        col.insert_many([
            {"id_canal": "EMA", "nombre": "Correo Electrónico"},
            {"id_canal": "CHAT", "nombre": "Chat en Vivo"},
            {"id_canal": "WHA", "nombre": "WhatsApp Business"},
            {"id_canal": "CAL", "nombre": "Llamada Telefónica"},
            {"id_canal": "VID", "nombre": "Videollamada Agendada"},
        ])
        docs = list(col.find({}, {"id_canal": 1, "nombre": 1}).sort("nombre", 1))
    return ok(serializar(docs))


@planes_bp.route("/planes", methods=["GET"])
@requiere_superadmin
def listar():
    solo_activos = request.args.get("solo_activos", "0") == "1"
    _, data = PlanController.listar(solo_activos=solo_activos)
    return ok(serializar(data))


@planes_bp.route("/planes/<plan_id>", methods=["GET"])
@requiere_superadmin
def obtener(plan_id):
    exito, data = PlanController.obtener(plan_id)
    if not exito: return err(data, 404)
    return ok(serializar(data))


@planes_bp.route("/planes", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or {}
    exito, resultado = PlanController.crear(datos, session["num_doc"])
    if not exito: return err(resultado)
    return ok(resultado)


@planes_bp.route("/planes/<plan_id>", methods=["PUT"])
@requiere_superadmin
def editar(plan_id):
    from app.configuracion.planes.model import PlanModel
    from app import db
    from bson import ObjectId

    datos = request.get_json(silent=True) or {}

    # Validar antes de cambiar a estado archivado (comparar por ID o por nombre)
    estado_nuevo = datos.get("estado", "")
    archivado_doc = db["estado_planes"].find_one({"nombre": "archivado"})
    archivado_id  = str(archivado_doc["_id"]) if archivado_doc else None
    if estado_nuevo and (estado_nuevo == "archivado" or estado_nuevo == archivado_id):
        plan = PlanModel.buscar_por_id(plan_id)
        if not plan:
            return err("Plan no encontrado", 404)

        plan_id_str = str(plan.get("_id"))

        empresas_con_plan = [
            e.get("razon_social", "Sin nombre")
            for e in db["empresas"].find({"activo": True, "plan": plan_id_str}, {"razon_social": 1})
        ]
        if empresas_con_plan:
            empresas_str = ", ".join(empresas_con_plan)
            return err(f"No puedes archivar este plan. Está asignado a: {empresas_str}. Debes cambiar el plan de esas empresas primero.")

    exito, resultado = PlanController.editar(plan_id, datos)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@planes_bp.route("/planes/<plan_id>", methods=["DELETE"])
@requiere_superadmin
def eliminar(plan_id):
    from app.configuracion.planes.model import PlanModel
    from app import db
    from bson import ObjectId

    plan = PlanModel.buscar_por_id(plan_id)
    if not plan:
        return err("Plan no encontrado", 404)

    plan_id_str = str(plan.get("_id"))

    empresas_con_plan = [
        e.get("razon_social", "Sin nombre")
        for e in db["empresas"].find({"activo": True, "plan": plan_id_str}, {"razon_social": 1})
    ]
    if empresas_con_plan:
        return err(
            f"No puedes eliminar este plan. Está asignado a: {', '.join(empresas_con_plan)}. "
            "Debes cambiar el plan de esas empresas primero."
        )

    exito, resultado = PlanController.archivar(plan_id)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@planes_bp.route("/planes/<plan_id>/en_uso", methods=["GET"])
@requiere_superadmin
def planes_verificar_en_uso(plan_id):
    from app.configuracion.planes.model import PlanModel
    from app import db
    from bson import ObjectId

    plan = PlanModel.buscar_por_id(plan_id)
    if not plan:
        return err("Plan no encontrado", 404)

    plan_id_str = str(plan.get("_id"))

    empresas_con_plan = list(db["empresas"].find(
        {"activo": True, "plan": plan_id_str}, {"razon_social": 1}
    ))
    count = len(empresas_con_plan)
    nombres_empresas = [e.get("razon_social", "Sin nombre") for e in empresas_con_plan]

    mensaje = ""
    if count > 0:
        empresas_str = ", ".join(nombres_empresas)
        mensaje = f"Este plan está asignado a: {empresas_str}. Debes cambiar el plan de esas empresas en **Empresas** antes de archivarlo."

    return ok({
        "en_uso": count > 0,
        "count": count,
        "empresas": nombres_empresas,
        "mensaje": mensaje if mensaje else None,
    })


# ── Helper público: qué módulos tiene habilitados una empresa ─────────────
# Útil para cualquier módulo del SaaS que necesite saber qué funcionalidades
# debe mostrar en el panel del cliente.

@planes_bp.route("/planes/modulos_empresa/<empresa_id>", methods=["GET"])
@requiere_superadmin
def modulos_empresa(empresa_id):
    modulos = PlanController.modulos_habilitados_por_empresa(empresa_id)
    return ok(modulos)
