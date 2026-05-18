"""
app/servicios/directorio/routes.py
API REST del módulo Directorio de Funcionarios y Órganos de Control.
Prefijo: /servicios/directorio
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_login, ok, err, serializar
from app.servicios.directorio.controller import CargoController, FuncionarioController

directorio_bp = Blueprint("directorio", __name__, url_prefix="/servicios/directorio")

def _usuario():
    """Devuelve el identificador del usuario activo de forma segura."""
    return session.get("num_doc") or session.get("usuario_id", "sistema")


# ── CARGOS ────────────────────────────────────────────────────────────────

@directorio_bp.route("/cargos", methods=["GET"])
@requiere_login
def listar_cargos():
    solo_activos = request.args.get("solo_activos", "1") == "1"
    _, lista = CargoController.listar(solo_activos=solo_activos)
    return ok(serializar(lista))


@directorio_bp.route("/cargos", methods=["POST"])
@requiere_login
def crear_cargo():
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = CargoController.crear(datos, _usuario())
    if not exito:
        return err(resultado)
    return ok(resultado, status=201)


@directorio_bp.route("/cargos/<cargo_id>", methods=["GET"])
@requiere_login
def obtener_cargo(cargo_id):
    exito, data = CargoController.obtener(cargo_id)
    if not exito:
        return err(data, 404)
    return ok(serializar(data))


@directorio_bp.route("/cargos/<cargo_id>", methods=["PUT"])
@requiere_login
def actualizar_cargo(cargo_id):
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = CargoController.actualizar(cargo_id, datos)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@directorio_bp.route("/cargos/<cargo_id>/estado", methods=["PATCH"])
@requiere_login
def estado_cargo(cargo_id):
    datos = request.get_json(silent=True) or {}
    activo = datos.get("activo", True)
    activo = activo if isinstance(activo, bool) else str(activo).lower() == "true"
    exito, resultado = CargoController.cambiar_estado(cargo_id, activo)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


# ── FUNCIONARIOS ──────────────────────────────────────────────────────────

@directorio_bp.route("/funcionarios", methods=["GET"])
@requiere_login
def listar_funcionarios():
    solo_activos = request.args.get("solo_activos", "1") == "1"
    _, lista = FuncionarioController.listar(solo_activos=solo_activos)
    return ok(serializar(lista))


@directorio_bp.route("/funcionarios", methods=["POST"])
@requiere_login
def crear_funcionario():
    datos = request.get_json(silent=True) or request.form.to_dict()
    ip = request.remote_addr or "desconocida"
    exito, resultado = FuncionarioController.crear(datos, _usuario(), ip)
    if not exito:
        return err(resultado)
    return ok(resultado, status=201)


@directorio_bp.route("/funcionarios/<funcionario_id>", methods=["GET"])
@requiere_login
def obtener_funcionario(funcionario_id):
    exito, data = FuncionarioController.obtener(funcionario_id)
    if not exito:
        return err(data, 404)
    return ok(serializar(data))


@directorio_bp.route("/funcionarios/<funcionario_id>", methods=["PUT"])
@requiere_login
def actualizar_funcionario(funcionario_id):
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = FuncionarioController.actualizar(funcionario_id, datos)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@directorio_bp.route("/funcionarios/<funcionario_id>/inactivar", methods=["PATCH"])
@requiere_login
def inactivar_funcionario(funcionario_id):
    """RN-DIR-03: inactivación histórica (nunca DELETE)."""
    datos = request.get_json(silent=True) or {}
    exito, resultado = FuncionarioController.inactivar(
        funcionario_id, datos.get("fecha_fin", ""), _usuario()
    )
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@directorio_bp.route("/funcionarios/<funcionario_id>/reactivar", methods=["PATCH"])
@requiere_login
def reactivar_funcionario(funcionario_id):
    exito, resultado = FuncionarioController.reactivar(funcionario_id)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)
