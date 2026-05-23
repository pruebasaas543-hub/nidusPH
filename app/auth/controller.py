"""
app/auth/controller.py
──────────────────────
Lógica de autenticación.
"""

import re
from flask import session
from app.auth.model import UserModel, SIGLAS_VALIDAS
from datetime import datetime, timedelta

_RE_OBJECT_ID = re.compile(r'^[0-9a-f]{24}$', re.I)


def _roles_sistema():
    from app.configuracion.roles.model import RolModel
    return RolModel.nombres_sistema()


def _resolver_nombre_rol(rol_asignado: str) -> str:
    """Devuelve el NOMBRE del rol dado su nombre o su ObjectId string."""
    if not rol_asignado:
        return ""
    if _RE_OBJECT_ID.match(str(rol_asignado)):
        from app import db
        from bson import ObjectId
        doc = db["roles"].find_one({"_id": ObjectId(rol_asignado)}, {"nombre": 1})
        return doc["nombre"] if doc else ""
    return str(rol_asignado)


class AuthController:

    @staticmethod
    def login(tipo_doc, num_doc, password, empresa_id=None):
        """
        Valida credenciales y establece sesión.
        Retorna (True, rol_o_centinela) o (False, mensaje_error).

        Centinela especial: '__SELECCIONAR_EMPRESA__' indica que el usuario
        tiene varias empresas y debe elegir desde /seleccionar-empresa.
        """

        # 1. Tipo de documento válido
        if tipo_doc not in SIGLAS_VALIDAS:
            return False, "Tipo de documento no válido"

        # 2. Buscar usuario
        usuario = UserModel.buscar_por_documento(tipo_doc, num_doc)
        if not usuario:
            return False, "Documento no encontrado en el sistema"

        if not usuario.get("activo"):
            return False, "Usuario inactivo. Contacte al administrador"

        # 3. Bloqueo temporal
        bloqueado_hasta = usuario.get("bloqueado_hasta")
        if bloqueado_hasta and datetime.utcnow() < bloqueado_hasta:
            minutos = max(1, int((bloqueado_hasta - datetime.utcnow()).seconds / 60))
            return False, f"Usuario bloqueado. Intente de nuevo en {minutos} minuto(s)"

        # 4. Contraseña
        if not UserModel.verificar_password(password, usuario["password"]):
            intentos = usuario.get("intentos_fallidos", 0) + 1
            campos_update = {"intentos_fallidos": intentos}
            if intentos >= 5:
                campos_update["bloqueado_hasta"] = datetime.utcnow() + timedelta(minutes=30)
                UserModel.actualizar_campos(num_doc, campos_update)
                return False, "Demasiados intentos fallidos. Cuenta bloqueada 30 minutos"
            UserModel.actualizar_campos(num_doc, campos_update)
            restantes = 5 - intentos
            return False, f"Contraseña incorrecta. {restantes} intento(s) restante(s)"

        # 5. Login exitoso
        UserModel.registrar_ultimo_login(num_doc)

        roles_sis = _roles_sistema()

        # ── Backward-compat: rol de sistema directo en users (pre-migración) ──
        rol_en_users = usuario.get("rol", "")
        if rol_en_users in roles_sis:
            session.update({
                "usuario_id":     str(usuario["_id"]),
                "rol":            rol_en_users,
                "es_sistema":     True,
                "num_doc":        usuario["numero_documento"],
                "tipo_doc":       usuario["tipo_documento"],
                "nombres":        usuario.get("nombres", ""),
                "primer_login":   bool(usuario.get("primer_login", False)),
                "empresa_id":     None,
                "empresa_nombre": None,
                "num_empresas":   0,
            })
            return True, rol_en_users

        # ── Resolver rol desde asociaciones (todos los usuarios post-migración) ──
        from app import db
        asociaciones = list(db["asociaciones"].aggregate([
            {"$match": {"user_id": usuario["_id"], "activo": True}},
            {"$lookup": {
                "from": "empresas",
                "localField": "empresa_id",
                "foreignField": "_id",
                "as": "empresa",
            }},
            {"$unwind": {"path": "$empresa", "preserveNullAndEmptyArrays": True}},
            {"$project": {
                "empresa_id":     1,
                "rol_asignado":   1,
                "empresa_nombre": "$empresa.razon_social",
                "empresa_slug":   "$empresa.slug",
            }},
            {"$sort": {"creado_en": 1}},
        ]))

        # ── Sistema via asociaciones (post-migración): empresa_id = null ──
        asoc_sistema = next(
            (a for a in asociaciones if a.get("empresa_id") is None), None
        )
        if asoc_sistema:
            nombre_rol = _resolver_nombre_rol(asoc_sistema.get("rol_asignado", ""))
            if nombre_rol in roles_sis:
                session.update({
                    "usuario_id":     str(usuario["_id"]),
                    "rol":            nombre_rol,
                    "es_sistema":     True,
                    "num_doc":        usuario["numero_documento"],
                    "tipo_doc":       usuario["tipo_documento"],
                    "nombres":        usuario.get("nombres", ""),
                    "primer_login":   bool(usuario.get("primer_login", False)),
                    "empresa_id":     None,
                    "empresa_nombre": None,
                    "num_empresas":   0,
                })
                return True, nombre_rol

        # ── Usuarios normales: solo asociaciones con empresa real ──
        asocs_empresa = [a for a in asociaciones if a.get("empresa_id") is not None]

        if not asocs_empresa:
            return False, "No tienes empresas asignadas. Contacta al administrador."

        # Datos base
        session.update({
            "usuario_id":   str(usuario["_id"]),
            "num_doc":      usuario["numero_documento"],
            "tipo_doc":     usuario["tipo_documento"],
            "nombres":      usuario.get("nombres", ""),
            "primer_login": bool(usuario.get("primer_login", False)),
            "num_empresas": len(asocs_empresa),
        })

        # Intentar auto-seleccionar empresa por contexto de slug
        asoc_sel = None
        if empresa_id:
            asoc_sel = next(
                (a for a in asocs_empresa if str(a["empresa_id"]) == str(empresa_id)),
                None
            )
            if not asoc_sel:
                # Vino de un slug específico pero no tiene acceso a esa empresa
                session.clear()
                return False, "No tienes acceso a esta empresa."
        elif len(asocs_empresa) == 1:
            asoc_sel = asocs_empresa[0]

        if asoc_sel:
            nombre_rol_sel = _resolver_nombre_rol(asoc_sel.get("rol_asignado", ""))
            session.update({
                "rol":            nombre_rol_sel,
                "empresa_id":     str(asoc_sel["empresa_id"]),
                "empresa_nombre": asoc_sel.get("empresa_nombre", ""),
                "empresa_slug":   asoc_sel.get("empresa_slug", ""),
            })
            return True, nombre_rol_sel

        # Múltiples empresas sin contexto: pedir selección
        session.update({
            "rol":            None,
            "empresa_id":     None,
            "empresa_nombre": None,
            "pendiente_seleccion": [
                {
                    "empresa_id":     str(a["empresa_id"]),
                    "empresa_nombre": a.get("empresa_nombre", ""),
                    "empresa_slug":   a.get("empresa_slug", ""),
                    "rol_asignado":   _resolver_nombre_rol(a.get("rol_asignado", "")),
                }
                for a in asocs_empresa
            ],
        })
        return True, "__SELECCIONAR_EMPRESA__"

    @staticmethod
    def logout():
        session.clear()
