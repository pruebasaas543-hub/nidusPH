"""
app/servicios/routes.py
"""

from flask import Blueprint, request, session, render_template
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.servicios.controller import ServicioController

servicios_bp = Blueprint("servicios", __name__, url_prefix="/servicios")
servicios_admin_bp = Blueprint("servicios_admin", __name__, url_prefix="/config/servicios")


# ── Panel de cada servicio (URL pública del módulo) ───────────────────────

@servicios_bp.route("/<codigo>/")
def panel_servicio(codigo):
    """Renderiza el panel de un servicio/módulo por su código.

    ─── CONTRATO PARA AGREGAR UN MÓDULO NUEVO (que no se vuelva a olvidar) ───
    1. Crear el doc en la colección `servicios` (con su `codigo`).
    2. Crear el blueprint bajo `/servicios/<codigo>/...` y registrarlo en app/__init__.py.
    3. Agregar aquí un `if codigo == "<codigo>": return render_template(...)`.
       Si no se agrega, cae al fallback `panel_servicio.html` ("EN DESARROLLO").
    NO hace falta tocar configuracion/panel.html: el panel del SuperAdmin abre
    CUALQUIER módulo con un iframe genérico a /servicios/<codigo>/ (ver
    ServiciosInicio.renderPaneles / _abrirModuloGenerico). El frontend es
    genérico; este dispatcher es la única fuente de verdad de qué se renderiza.
    """
    from app.servicios.model import ServicioModel
    from flask import abort
    srv = ServicioModel.buscar_por_codigo(codigo)
    if not srv:
        abort(404)
    if codigo == "contabilidad_financiera":
        return render_template("servicios/contabilidad.html", servicio=srv)
    if codigo == "directorio":
        es_sistema = session.get("es_sistema", False)
        empresa_id = session.get("empresa_id", "")
        from app.autenticacion.routes import _tema_efectivo
        tema_clave, tema_css, tema_vars = _tema_efectivo(empresa_id)
        if not es_sistema:
            from app.servicios.permisos.model import PermisosRolModel
            rol      = session.get("rol", "")
            permisos = PermisosRolModel.obtener_para_sesion(empresa_id, rol, "directorio")
            return render_template("servicios/directorio_usuario.html",
                                   servicio=srv, permisos=permisos,
                                   empresa_id=empresa_id,
                                   tema_clave=tema_clave, tema_css=tema_css,
                                   tema_vars=tema_vars)
        return render_template("servicios/directorio.html", servicio=srv,
                               tema_clave=tema_clave, tema_css=tema_css,
                               tema_vars=tema_vars)
    if codigo == "boton_panico":
        import logging
        from app.configuracion.roles.model import RolModel
        from app.autenticacion.routes import _tema_efectivo
        rol = session.get("rol", "")
        nombres = RolModel.nombres_sistema()
        es_sistema = rol in nombres
        empresa_id = session.get("empresa_id", "")
        tema_clave, tema_css, tema_vars = _tema_efectivo(empresa_id)
        if es_sistema:
            permisos = {"emergencia": True, "configuracion": True, "log": True}
        else:
            from app.servicios.permisos.model import PermisosRolModel
            permisos = PermisosRolModel.obtener_para_sesion(empresa_id, rol, "boton_panico")
        logging.getLogger(__name__).info("boton_panico → rol=%r es_sistema=%s permisos=%s", rol, es_sistema, permisos)
        return render_template("servicios/boton_panico.html", servicio=srv,
                               es_sistema=es_sistema, empresa_id=empresa_id, permisos=permisos,
                               tema_clave=tema_clave, tema_css=tema_css, tema_vars=tema_vars)
    if codigo == "control_acceso":
        from app.configuracion.roles.model import RolModel
        from app.autenticacion.routes import _tema_efectivo
        rol = session.get("rol", "")
        es_sistema = rol in RolModel.nombres_sistema()
        empresa_id = session.get("empresa_id", "")
        tema_clave, tema_css, tema_vars = _tema_efectivo(empresa_id)
        # ?vista= fuerza una vista (lo usan los iframes del dashboard admin).
        # Si no, se elige por rol: Residente → credenciales; Admin/Sistema → dashboard
        # completo (todas las pestañas); Vigilancia y demás → portería.
        vista = request.args.get("vista", "")
        _mapa = {
            "porteria":       "servicios/control_acceso_porteria.html",
            "credenciales":   "servicios/control_acceso_residente.html",
            "monitoreo":      "servicios/control_acceso_monitoreo.html",
            "configuracion":  "servicios/control_acceso_config.html",
        }
        if vista in _mapa:
            plantilla = _mapa[vista]
        elif rol == "Residente":
            plantilla = "servicios/control_acceso_residente.html"
        elif es_sistema or rol == "Administrador de la Copropiedad":
            plantilla = "servicios/control_acceso_admin.html"
        else:
            plantilla = "servicios/control_acceso_porteria.html"
        return render_template(plantilla, servicio=srv,
                               es_sistema=es_sistema, empresa_id=empresa_id, rol=rol,
                               tema_clave=tema_clave, tema_css=tema_css, tema_vars=tema_vars)
    return render_template("servicios/panel_servicio.html", servicio=srv)


# ── API de gestión (superadmin) ───────────────────────────────────────────

@servicios_admin_bp.route("", methods=["GET"])
@requiere_superadmin
def listar():
    solo_activos = request.args.get("solo_activos", "1") == "1"
    _, lista = ServicioController.listar(solo_activos=solo_activos)
    return ok(serializar(lista))


@servicios_admin_bp.route("", methods=["POST"])
@requiere_superadmin
def crear():
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = ServicioController.crear(datos, session["num_doc"])
    if not exito:
        return err(resultado)
    return ok(resultado)


@servicios_admin_bp.route("/<servicio_id>", methods=["GET"])
@requiere_superadmin
def obtener(servicio_id):
    exito, data = ServicioController.obtener(servicio_id)
    if not exito:
        return err(data, 404)
    return ok(serializar(data))


@servicios_admin_bp.route("/<servicio_id>", methods=["PUT"])
@requiere_superadmin
def actualizar(servicio_id):
    datos = request.get_json(silent=True) or request.form.to_dict()
    exito, resultado = ServicioController.actualizar(servicio_id, datos)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@servicios_admin_bp.route("/<servicio_id>/estado", methods=["PATCH"])
@requiere_superadmin
def cambiar_estado(servicio_id):
    datos = request.get_json(silent=True) or {}
    activo = bool(datos.get("activo", True))
    exito, resultado = ServicioController.cambiar_estado(servicio_id, activo)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)


@servicios_admin_bp.route("/<servicio_id>/en_uso", methods=["GET"])
@requiere_superadmin
def verificar_en_uso(servicio_id):
    from app.servicios.model import ServicioModel
    from app import db
    from bson import ObjectId

    servicio = ServicioModel.obtener(servicio_id)
    if not servicio:
        return err("Servicio no encontrado", 404)

    nombre_servicio = servicio.get("nombre", "").strip()
    servicio_oid = servicio.get("_id")

    servicio_id_str = str(servicio_oid)

    # Buscar en roles por ID del servicio
    roles_con_modulo = list(db["roles"].find({
        "modulos": servicio_id_str,
        "activo": True
    }, {"_id": 1, "nombre": 1}))

    count_roles = len(roles_con_modulo)
    nombres_roles = [r.get("nombre", "Sin nombre") for r in roles_con_modulo]

    # Buscar en planes por ID del servicio
    planes_con_modulo = list(db["planes_saas"].find({
        "modulos_incluidos": servicio_id_str
    }, {"_id": 1, "nombre": 1, "estado": 1}))

    count_planes = len(planes_con_modulo)
    nombres_planes = [p.get("nombre", "Sin nombre") for p in planes_con_modulo]

    total_en_uso = count_roles + count_planes
    mensaje = ""

    if count_roles > 0:
        roles_str = ", ".join(nombres_roles)
        mensaje += f"Está asignado a los roles: {roles_str}. "

    if count_planes > 0:
        planes_str = ", ".join(nombres_planes)
        mensaje += f"Está incluido en los planes: {planes_str}. "

    if mensaje:
        mensaje += "Debes quitarlo de Roles y Planes antes de inactivarlo."

    return ok({
        "en_uso": total_en_uso > 0,
        "count": total_en_uso,
        "count_roles": count_roles,
        "count_planes": count_planes,
        "roles": nombres_roles,
        "planes": nombres_planes,
        "mensaje": mensaje if mensaje else None
    })


@servicios_admin_bp.route("/<servicio_id>", methods=["DELETE"])
@requiere_superadmin
def eliminar(servicio_id):
    from app.servicios.model import ServicioModel
    from app import db

    servicio = ServicioModel.obtener(servicio_id)
    if not servicio:
        return err("Servicio no encontrado", 404)

    nombre_servicio = servicio.get("nombre", "").strip()
    servicio_oid    = servicio.get("_id")

    servicio_id_str = str(servicio_oid)

    roles_en_uso = db["roles"].count_documents({
        "modulos": servicio_id_str,
        "activo": True,
    })
    planes_en_uso = db["planes_saas"].count_documents({
        "modulos_incluidos": servicio_id_str
    })

    if roles_en_uso or planes_en_uso:
        partes = []
        if roles_en_uso:
            partes.append(f"{roles_en_uso} rol(es)")
        if planes_en_uso:
            partes.append(f"{planes_en_uso} plan(es)")
        return err(
            f"No se puede eliminar: el servicio está asignado a {' y '.join(partes)}. "
            "Quítalo de Roles y Planes antes de eliminarlo."
        )

    exito, resultado = ServicioController.eliminar(servicio_id)
    if not exito:
        return err(resultado)
    return ok(mensaje=resultado)
