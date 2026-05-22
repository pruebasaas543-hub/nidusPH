"""
app/configuracion/roles/routes.py
"""

from flask import Blueprint, request, session
from app.configuracion.utils import requiere_superadmin, ok, err, serializar
from app.configuracion.roles.controller import RolController, HabilitacionRolController
from app.configuracion.roles.model import MODULOS_SISTEMA

roles_bp = Blueprint("config_roles", __name__, url_prefix="/config")


# ── Roles ─────────────────────────────────────────────────────────────────

@roles_bp.route("/roles", methods=["GET"])
@requiere_superadmin
def roles_listar():
    todos              = request.args.get("todos",             "0") == "1"
    excluir_internos   = request.args.get("excluir_internos",  "0") == "1"
    _, data = RolController.listar(solo_activos=not todos, excluir_internos=excluir_internos)
    return ok(serializar(data))


@roles_bp.route("/roles", methods=["POST"])
@requiere_superadmin
def roles_crear():
    datos = request.get_json(silent=True) or {}
    exito, resultado = RolController.crear(datos, session["num_doc"])
    if not exito: return err(resultado)
    return ok(resultado)


@roles_bp.route("/roles/<rol_id>", methods=["PUT"])
@requiere_superadmin
def roles_editar(rol_id):
    datos = request.get_json(silent=True) or {}
    exito, resultado = RolController.editar(rol_id, datos)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@roles_bp.route("/roles/<rol_id>", methods=["DELETE"])
@requiere_superadmin
def roles_eliminar(rol_id):
    exito, resultado = RolController.eliminar(rol_id)
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@roles_bp.route("/roles/<rol_id>/en_uso", methods=["GET"])
@requiere_superadmin
def roles_verificar_en_uso(rol_id):
    from app.configuracion.roles.model import RolModel
    from app import db
    from bson import ObjectId

    rol = RolModel.buscar_por_id(rol_id)
    if not rol:
        return err("Rol no encontrado", 404)

    nombre_rol = rol.get("nombre", "")
    rol_oid    = rol.get("_id")

    # ── 1. Verificar si el rol está habilitado en alguna empresa ──────────
    habs_con_rol = list(db["habilitacion_roles"].find(
        {"roles_activos": str(rol_oid)}, {"empresa_id": 1}
    ))

    if habs_con_rol:
        empresa_ids = [h["empresa_id"] for h in habs_con_rol]
        empresas = []
        for eid in empresa_ids:
            try:
                emp = db["empresas"].find_one({"_id": ObjectId(str(eid))}, {"razon_social": 1})
                empresas.append(emp.get("razon_social", str(eid)) if emp else str(eid))
            except Exception:
                empresas.append(str(eid))

        empresas_info = "\n  • ".join(empresas)
        mensaje = (
            f"El rol '{nombre_rol}' está habilitado en {len(empresas)} empresa(s):\n\n"
            f"  • {empresas_info}\n\n"
            f"Debes quitar este rol de esas empresas en 'Roles por Empresa' antes de inactivarlo."
        )
        return ok({
            "en_uso":   True,
            "motivo":   "habilitacion",
            "count":    len(empresas),
            "empresas": empresas,
            "mensaje":  mensaje,
        })

    # ── 2. Verificar si el rol está asignado a algún usuario ─────────────
    todas_asociaciones = list(db["asociaciones"].find(
        {"activo": True}, {"rol_asignado": 1, "user_id": 1, "empresa_id": 1}
    ))

    asociaciones_con_rol = []
    for asoc in todas_asociaciones:
        rol_asoc = asoc.get("rol_asignado", "")
        if (rol_asoc == nombre_rol or
                rol_asoc == str(rol_oid) or
                str(rol_asoc) == str(rol_oid)):
            user_id_val = asoc.get("user_id", "")
            try:
                usuario_oid  = user_id_val if hasattr(user_id_val, 'generation_time') else ObjectId(str(user_id_val))
                usuario      = db["users"].find_one({"_id": usuario_oid}, {"nombres": 1, "apellidos": 1, "numero_documento": 1})
                if usuario:
                    usuario_nombre = f"{usuario.get('nombres','')} {usuario.get('apellidos','')}".strip() or str(user_id_val)
                else:
                    usuario_nombre = str(user_id_val)
            except Exception:
                usuario_nombre = str(user_id_val)

            asociaciones_con_rol.append({
                "usuario_id":     str(user_id_val),
                "usuario_nombre": usuario_nombre,
                "empresa_id":     str(asoc.get("empresa_id", "")),
            })

    count         = len(asociaciones_con_rol)
    usuarios_info = "\n  • ".join([a.get("usuario_nombre", "Desconocido") for a in asociaciones_con_rol])

    mensaje = ""
    if count > 0:
        mensaje = (
            f"El rol '{nombre_rol}' está asignado a {count} usuario(s):\n\n"
            f"  • {usuarios_info}\n\n"
            f"Debes desasociar estos usuarios antes de inactivar el rol."
        )

    return ok({
        "en_uso":  count > 0,
        "motivo":  "asociacion" if count > 0 else None,
        "count":   count,
        "asociaciones": [{"usuario_nombre": a.get("usuario_nombre"), "usuario_id": a.get("usuario_id")} for a in asociaciones_con_rol],
        "mensaje": mensaje if mensaje else None,
    })


# ── Habilitación de roles por empresa ─────────────────────────────────────

@roles_bp.route("/habilitacion", methods=["GET"])
@requiere_superadmin
def habilitacion_todas():
    from app import db
    from bson import ObjectId
    from app.configuracion.roles.model import RolModel
    docs = list(db["habilitacion_roles"].find({}))
    roles_idx = {str(r["_id"]): r.get("nombre", "") for r in RolModel.listar(solo_activos=False, excluir_internos=True)}
    resultado = []
    for d in docs:
        emp_id = str(d.get("empresa_id", ""))
        emp = db["empresas"].find_one({"_id": d["empresa_id"]}, {"razon_social": 1, "activo": 1}) if d.get("empresa_id") else None
        resultado.append({
            "empresa_id":    emp_id,
            "razon_social":  emp.get("razon_social", "") if emp else "—",
            "empresa_activa": emp.get("activo", False) if emp else False,
            "roles_activos": d.get("roles_activos", []),
            "roles_nombres": [roles_idx.get(r, r) for r in d.get("roles_activos", [])],
            "creado_en":          serializar(d.get("creado_en")),
            "actualizado_en":     serializar(d.get("actualizado_en")),
            "id_actualizado_por": d.get("id_actualizado_por", ""),
        })
    resultado.sort(key=lambda x: x["razon_social"].lower())
    return ok(resultado)


@roles_bp.route("/habilitacion/<empresa_id>", methods=["GET"])
@requiere_superadmin
def habilitacion_obtener(empresa_id):
    exito, data = HabilitacionRolController.obtener(empresa_id)
    if not exito: return err(data)
    return ok(serializar(data))


@roles_bp.route("/habilitacion/<empresa_id>", methods=["POST"])
@requiere_superadmin
def habilitacion_guardar(empresa_id):
    from app import db
    from bson import ObjectId

    body = request.get_json(silent=True) or {}
    roles_nuevos = body.get("roles_activos", [])
    if not isinstance(roles_nuevos, list):
        return err("roles_activos debe ser lista")

    # Detectar roles que se están quitando
    config_actual = db["habilitacion_roles"].find_one({"empresa_id": ObjectId(empresa_id)})
    roles_actuales = config_actual.get("roles_activos", []) if config_actual else []
    roles_quitados = [r for r in roles_actuales if r not in roles_nuevos]

    if roles_quitados:
        # Verificar si algún usuario en esta empresa tiene uno de esos roles
        try:
            empresa_oid = ObjectId(empresa_id)
        except Exception:
            empresa_oid = empresa_id

        # Construir mapa ID → nombre para resolver roles almacenados como IDs
        roles_docs = list(db["roles"].find({}, {"_id": 1, "nombre": 1}))
        id_a_nombre = {str(r["_id"]): r.get("nombre", "") for r in roles_docs}

        conflictos = []
        for rol_id in roles_quitados:
            rol_nombre = id_a_nombre.get(rol_id, rol_id)
            asocs = list(db["asociaciones"].find(
                {"empresa_id": empresa_oid, "rol_asignado": {"$in": [rol_nombre, rol_id]}, "activo": True},
                {"user_id": 1}
            ))
            for asoc in asocs:
                usuario = db["users"].find_one(
                    {"_id": asoc["user_id"]},
                    {"nombres": 1, "apellidos": 1, "numero_documento": 1}
                )
                if usuario:
                    nombre = f"{usuario.get('nombres','')} {usuario.get('apellidos','')}".strip()
                    doc    = usuario.get("numero_documento", "")
                    conflictos.append({"rol": rol_nombre, "usuario": nombre or doc, "doc": doc})

        if conflictos:
            detalle = "\n".join(
                f"  • Rol '{c['rol']}' → {c['usuario']} ({c['doc']})" for c in conflictos
            )
            return err(
                f"No se puede quitar el(los) rol(es) porque hay usuarios asociados:\n\n{detalle}\n\n"
                f"Elimina primero esas asociaciones en 'Asociacion Usuario Empresa Rol'."
            )

    exito, resultado = HabilitacionRolController.guardar(
        empresa_id, roles_nuevos, session.get("usuario_id", "")
    )
    if not exito: return err(resultado)
    return ok(mensaje=resultado)


@roles_bp.route("/habilitacion/<empresa_id>", methods=["DELETE"])
@requiere_superadmin
def habilitacion_eliminar(empresa_id):
    from app import db
    from bson import ObjectId
    try:
        result = db["habilitacion_roles"].delete_one({"empresa_id": ObjectId(empresa_id)})
    except Exception:
        return err("ID de empresa inválido")
    if result.deleted_count == 0:
        return err("No existe configuración para esta empresa")
    return ok(mensaje="Configuración de roles eliminada")
