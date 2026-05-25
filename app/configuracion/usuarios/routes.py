"""
app/configuracion/usuarios/routes.py
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.configuracion.usuarios.controller import UsuarioController

usuarios_bp = Blueprint("config_usuarios", __name__, url_prefix="/config")


@usuarios_bp.route("/usuarios", methods=["GET"])
@requiere_superadmin
def listar():
    _, data = UsuarioController.listar()
    return ok(serializar(data))


@usuarios_bp.route("/usuarios", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = UsuarioController.crear(
        datos,
        creado_por    = session["num_doc"],
        creado_por_id = session.get("usuario_id", ""),
        rol_sesion    = session.get("rol", ""),
    )
    if not exito: return err(resultado)
    return ok(resultado)


@usuarios_bp.route("/usuarios/normalizar-schema", methods=["POST"])
@requiere_superadmin
def normalizar_schema():
    from app.configuracion.usuarios.model import UsuarioConfigModel
    modificados = UsuarioConfigModel.normalizar_schema()
    return ok(mensaje=f"Normalización completada: {modificados} documento(s) actualizados")


@usuarios_bp.route("/usuarios/migrar-schema", methods=["POST"])
@requiere_superadmin
def migrar_schema():
    from app.configuracion.usuarios.model import UsuarioConfigModel
    resultado = UsuarioConfigModel.migrar_a_esquema_limpio()
    return ok(resultado, mensaje=(
        f"Migración completada: {resultado['asoc_sistema_creadas']} asoc. sistema creadas, "
        f"{resultado['asoc_normalizadas']} asoc. normalizadas, "
        f"{resultado['users_actualizados']} usuarios actualizados"
    ))


@usuarios_bp.route("/usuarios/<user_id>", methods=["GET"])
@requiere_superadmin
def obtener(user_id):
    from app import db
    from bson import ObjectId
    from app.configuracion.usuarios.model import UsuarioConfigModel
    usuario = UsuarioConfigModel.buscar_por_id(user_id)
    if not usuario:
        return err("Usuario no encontrado")
    for campo in ("password", "token_recuperacion", "bloqueado_hasta",
                  "intentos_fallidos", "token_expira"):
        usuario.pop(campo, None)
    try:
        asocs = list(db["asociaciones"].find(
            {"user_id": ObjectId(user_id), "activo": True},
            {"_id": 0, "empresa_id": 1, "rol_asignado": 1}
        ))
        usuario["asociaciones"] = [
            {"empresa_id": str(a["empresa_id"]) if a.get("empresa_id") else None,
             "rol_asignado": a.get("rol_asignado", "")}
            for a in asocs
        ]
    except Exception:
        usuario["asociaciones"] = []
    return ok(serializar(usuario))


@usuarios_bp.route("/usuarios/<user_id>", methods=["PUT"])
@requiere_superadmin
def editar(user_id):
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = UsuarioController.editar(user_id, datos)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@usuarios_bp.route("/usuarios/<user_id>/estado", methods=["PATCH"])
@requiere_superadmin
def estado(user_id):
    body = request.get_json(silent=True) or {}
    exito, resultado = UsuarioController.cambiar_estado(user_id, bool(body.get("activo", True)))
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@usuarios_bp.route("/usuarios/<user_id>/reset", methods=["POST"])
@requiere_superadmin
def reset(user_id):
    exito, resultado = UsuarioController.resetear_password(user_id)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@usuarios_bp.route("/usuarios/<user_id>", methods=["DELETE"])
@requiere_superadmin
def eliminar(user_id):
    exito, resultado = UsuarioController.eliminar(user_id)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@usuarios_bp.route("/usuarios/roles-sistema", methods=["GET"])
@requiere_superadmin
def roles_sistema():
    from app.configuracion.roles.model import RolModel
    roles = RolModel.roles_sistema_asignables(session.get("rol", ""))
    return ok(serializar(roles))


@usuarios_bp.route("/usuarios/diagnostico-sistema", methods=["GET"])
@requiere_superadmin
def diagnostico_sistema():
    from app import db
    from app.configuracion.roles.model import RolModel
    roles_sis = RolModel.nombres_sistema()
    pipeline = [
        {"$match": {"empresa_id": None, "activo": True}},
        {"$lookup": {
            "from": "users",
            "localField": "user_id",
            "foreignField": "_id",
            "as": "usuario",
        }},
        {"$unwind": "$usuario"},
        {"$project": {
            "_id": 0,
            "user_id":        {"$toString": "$user_id"},
            "num_doc":        "$usuario.numero_documento",
            "nombres":        "$usuario.nombres",
            "apellidos":      "$usuario.apellidos",
            "rol_asignado":   1,
            "rol_es_sistema": {"$in": ["$rol_asignado", list(roles_sis)]},
            "creado_en":      1,
        }},
        {"$sort": {"rol_asignado": 1}},
    ]
    resultado = list(db["asociaciones"].aggregate(pipeline))
    return ok(serializar(resultado))


@usuarios_bp.route("/usuarios/<user_id>/rol-sistema", methods=["POST"])
@requiere_superadmin
def asignar_rol_sistema(user_id):
    body = request.get_json(silent=True) or {}
    rol_nombre = (body.get("rol_nombre") or "").strip()
    if not rol_nombre:
        return err("Se requiere rol_nombre")
    exito, resultado = UsuarioController.asignar_rol_sistema(
        user_id, rol_nombre, session["num_doc"], session.get("rol", "")
    )
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@usuarios_bp.route("/usuarios/<user_id>/rol-sistema", methods=["DELETE"])
@requiere_superadmin
def quitar_rol_sistema(user_id):
    exito, resultado = UsuarioController.quitar_rol_sistema(user_id, session["num_doc"])
    if not exito: return err(resultado)
    return ok(mensaje=resultado)
