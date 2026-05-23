"""
app/configuracion/utils.py
──────────────────────────
Helpers y decoradores compartidos por todos los sub-módulos de configuración.
Importar desde aquí evita duplicación entre routes.
"""

import re
from functools import wraps
from flask import session, jsonify
from bson import ObjectId
from datetime import datetime

MAX_IMG_BYTES   = 3 * 1024 * 1024
ALLOWED_IMG_EXT = {"png", "jpg", "jpeg", "svg", "webp", "gif"}


# ── Decoradores ───────────────────────────────────────────────────────────

def requiere_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            return jsonify({"ok": False, "error": "No autenticado"}), 401
        return f(*args, **kwargs)
    return wrapper


def requiere_superadmin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        from flask import request as _req
        es_api = _req.path.startswith("/cont/") or _req.path.startswith("/config/") and _req.method != "GET"
        if "usuario_id" not in session:
            if es_api or _req.is_json or _req.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "error": "No autenticado"}), 401
            from flask import redirect, url_for
            return redirect(url_for("auth.login_get"))
        # es_sistema en sesión (post-login con nuevo código); fallback para sesiones antiguas
        tiene_acceso = session.get("es_sistema") or (
            "es_sistema" not in session and
            session.get("rol") in __import__(
                "app.configuracion.roles.model", fromlist=["RolModel"]
            ).RolModel.nombres_sistema()
        )
        if not tiene_acceso:
            if es_api or _req.is_json or _req.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"ok": False, "error": "Acceso denegado"}), 403
            from flask import redirect, url_for
            return redirect(url_for("auth.login_get"))
        return f(*args, **kwargs)
    return wrapper


def requiere_roles(*roles_permitidos):
    """Decorador flexible: permite pasar uno o varios roles."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "usuario_id" not in session:
                return jsonify({"ok": False, "error": "No autenticado"}), 401
            if session.get("rol") not in roles_permitidos:
                return jsonify({"ok": False, "error": "Acceso denegado"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── Respuestas JSON ───────────────────────────────────────────────────────

def ok(data=None, mensaje=None, status=200):
    r = {"ok": True}
    if data    is not None: r["data"]    = data
    if mensaje is not None: r["mensaje"] = mensaje
    return jsonify(r), status


def err(msg, status=400):
    return jsonify({"ok": False, "error": msg}), status


def serializar(obj):
    """Convierte ObjectId, datetime y bytes a tipos JSON-serializables."""
    if isinstance(obj, list):     return [serializar(i) for i in obj]
    if isinstance(obj, dict):     return {k: serializar(v) for k, v in obj.items()}
    if isinstance(obj, ObjectId): return str(obj)
    if isinstance(obj, datetime): return obj.strftime("%Y-%m-%d %H:%M")
    if isinstance(obj, bytes):    return obj.decode("utf-8", errors="ignore")
    return obj


# ── Validadores ───────────────────────────────────────────────────────────

def email_ok(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email.strip()))


def color_ok(val: str) -> bool:
    return bool(re.match(r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$", val.strip()))


def imagen_ok(file_storage, nombre_campo: str):
    """Retorna (True, None) si ok o no hay archivo; (False, msg) si hay error."""
    if not file_storage or not file_storage.filename:
        return True, None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_IMG_EXT:
        return False, f"'{nombre_campo}': formato no permitido (PNG, JPG, SVG, WEBP)"
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_IMG_BYTES:
        return False, f"'{nombre_campo}': tamaño máximo 3 MB"
    return True, None
