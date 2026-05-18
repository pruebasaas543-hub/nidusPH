"""
app/contabilidad/__init__.py
─────────────────────────────
Ensamblador de blueprints del módulo de Contabilidad Financiera.
Cada sub-módulo registra su propio Blueprint; este archivo los agrupa
para que app/__init__.py los pueda registrar con una sola llamada.
"""

from app.contabilidad.puc.routes         import puc_bp
from app.contabilidad.periodos.routes    import periodos_bp
from app.contabilidad.comprobantes.routes import comprobantes_bp
from app.contabilidad.cartera.routes     import cartera_bp
from app.contabilidad.tesoreria.routes   import tesoreria_bp
from app.contabilidad.presupuesto.routes import presupuesto_bp
from app.contabilidad.activos.routes     import activos_bp
from app.contabilidad.reportes.routes    import reportes_bp


def register_contabilidad_blueprints(app):
    """Registra todos los blueprints de contabilidad en la app Flask."""
    for bp in [
        puc_bp,
        periodos_bp,
        comprobantes_bp,
        cartera_bp,
        tesoreria_bp,
        presupuesto_bp,
        activos_bp,
        reportes_bp,
    ]:
        app.register_blueprint(bp)

    app.logger.info("Blueprints de contabilidad registrados: %d sub-módulos", 8)
