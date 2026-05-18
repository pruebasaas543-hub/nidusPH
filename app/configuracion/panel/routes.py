"""
app/configuracion/panel/routes.py
─────────────────────────────────
Vista principal del panel de configuración.
Renderiza el HTML; todo lo demás pasa por las APIs JSON de cada sub-módulo.
"""

from flask import Blueprint, render_template, session
from app.configuracion.utils import requiere_superadmin
from app.configuracion.catalogos.model import CatalogoModel

panel_bp = Blueprint("config_panel", __name__, url_prefix="/config")


@panel_bp.route("/", methods=["GET"])
@requiere_superadmin
def panel():
    return render_template(
        "configuracion/panel.html",
        nombres = session.get("nombres", "SuperAdmin"),
        rol     = session.get("rol", "SuperAdmin"),
        num_doc = session.get("num_doc", ""),
        modulos = CatalogoModel.modulos_sistema(),
    )
