"""
app/configuracion/__init__.py
─────────────────────────────
Ensamblador de blueprints de configuración.
Cada sub-módulo registra su propio Blueprint; este archivo los agrupa
para que app/__init__.py los pueda registrar con una sola llamada.
"""

from app.configuracion.panel.routes          import panel_bp
from app.configuracion.empresas.routes       import empresas_bp
from app.configuracion.usuarios.routes       import usuarios_bp
from app.configuracion.asociaciones.routes   import asociaciones_bp
from app.configuracion.roles.routes          import roles_bp
from app.configuracion.datos_ph.routes       import datos_ph_bp
from app.configuracion.pagos.routes          import pagos_bp
from app.configuracion.planes.routes         import planes_bp
from app.configuracion.apariencias.routes         import apariencias_bp
from app.configuracion.apariencia_empresa.routes  import apariencia_empresa_bp
from app.configuracion.directorio.routes          import directorio_cfg_bp


def register_config_blueprints(app):
    """Registra todos los blueprints de configuración en la app."""
    for bp in [
        panel_bp,
        empresas_bp,
        usuarios_bp,
        asociaciones_bp,
        roles_bp,
        datos_ph_bp,
        pagos_bp,
        planes_bp,
        apariencias_bp,
        apariencia_empresa_bp,
        directorio_cfg_bp,
    ]:
        app.register_blueprint(bp)

    app.logger.info("Blueprints de configuración registrados: %d sub-módulos", 11)
