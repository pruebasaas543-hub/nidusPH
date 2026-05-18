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
    from app.configuracion.usuarios.model import UsuarioConfigModel
    UsuarioConfigModel.normalizar_schema()
    _, data = UsuarioController.listar()
    return ok(serializar(data))


@usuarios_bp.route("/usuarios", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = UsuarioController.crear(datos, session["num_doc"])
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
    rol_sesion = session.get("rol", "")
    roles = list(RolModel.listar(solo_activos=True))
    roles_sis = [r for r in roles if r.get("es_sistema")]
    # Solo SuperAdmin puede ver y asignar SuperAdmin
    if rol_sesion != "SuperAdmin":
        roles_sis = [r for r in roles_sis if r["nombre"] != "SuperAdmin"]
    return ok(serializar(roles_sis))


@usuarios_bp.route("/usuarios/<user_id>/rol-sistema", methods=["POST"])
@requiere_superadmin
def asignar_rol_sistema(user_id):
    body = request.get_json(silent=True) or {}
    rol_nombre = (body.get("rol_nombre") or "").strip()
    if not rol_nombre:
        return err("Se requiere rol_nombre")
    exito, resultado = UsuarioController.asignar_rol_sistema(user_id, rol_nombre, session["num_doc"])
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@usuarios_bp.route("/usuarios/<user_id>/rol-sistema", methods=["DELETE"])
@requiere_superadmin
def quitar_rol_sistema(user_id):
    exito, resultado = UsuarioController.quitar_rol_sistema(user_id, session["num_doc"])
    if not exito: return err(resultado)
    return ok(mensaje=resultado)
