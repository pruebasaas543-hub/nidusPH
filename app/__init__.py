"""
app/__init__.py
───────────────
Factory principal de la aplicación Flask.
Inicializa: MongoDB, Flask-Mail, Logging y todos los Blueprints.
"""

import os
import logging
import logging.handlers

from flask import Flask
from pymongo import MongoClient
from config import Config
from flask_mail import Mail

# Variables globales (se llenan en create_app)
mongo_client = None
db           = None
mail         = Mail()


def _configurar_logging(app: Flask):
    """Configura logging: consola + archivo rotativo."""
    nivel = logging.DEBUG if app.config.get("DEBUG") else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(nivel)

    os.makedirs("logs", exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        "logs/app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(nivel)

    root_logger = logging.getLogger()
    root_logger.setLevel(nivel)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silenciar libs verbosas
    for lib in ["pymongo", "urllib3", "twilio"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    app.logger.info("Logging inicializado (nivel=%s)", logging.getLevelName(nivel))


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    # ── Flask-Mail ─────────────────────────────────────────────────────────
    app.config["MAIL_SERVER"]         = os.environ.get("MAIL_SERVER",  "smtp.gmail.com")
    app.config["MAIL_PORT"]           = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"]        = os.environ.get("MAIL_USE_TLS", "True") == "True"
    app.config["MAIL_USERNAME"]       = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"]       = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get(
        "MAIL_DEFAULT_SENDER", os.environ.get("MAIL_USERNAME")
    )
    mail.init_app(app)

    # ── Logging ────────────────────────────────────────────────────────────
    _configurar_logging(app)

    # ── MongoDB ────────────────────────────────────────────────────────────
    global mongo_client, db
    mongo_client = MongoClient(app.config["MONGO_URI"])
    db = mongo_client[app.config["DB_NAME"]]
    app.logger.info("Conectado a MongoDB: '%s'", app.config["DB_NAME"])

    # Tipos de documento desde MongoDB (debe ir antes de registrar blueprints)
    from app.autenticacion.model import reload_tipos_documento
    reload_tipos_documento()

    # Índices
    db["users"].create_index(
        [("tipo_documento", 1), ("numero_documento", 1)], unique=True
    )
    db["users"].create_index("email",              sparse=True)
    db["users"].create_index("token_recuperacion", sparse=True)
    db["empresas"].create_index("slug",            unique=True, sparse=True)
    db["empresas"].create_index("nit",             unique=True, sparse=True)
    db["roles"].create_index("nombre",             unique=True)
    db["planes_saas"].create_index("plan_id",      unique=True, sparse=True)

    # ── Índice único para servicios ────────────────────────────────────────
    db["servicios"].create_index("codigo", unique=True, sparse=True)

    # ── Índices para directorio ────────────────────────────────────────────
    db["directorio_contactos"].create_index([("empresa_id", 1), ("bloque", 1), ("orden", 1)])

    # ── Índices para botón de pánico ───────────────────────────────────────
    db["panic_configurations"].create_index([("empresa_id", 1), ("residente_id", 1)], unique=True)
    db["panic_events"].create_index([("empresa_id", 1), ("residente_id", 1), ("activado_en", -1)])

    # ── Blueprints ─────────────────────────────────────────────────────────
    from app.autenticacion.routes            import auth_bp
    from app.recuperacion.routes    import recuperacion_bp
    from app.slug.routes            import slug_bp
    from app.configuracion          import register_config_blueprints
    from app.servicios.routes               import servicios_bp, servicios_admin_bp
    from app.servicios.directorio.routes    import directorio_bp
    from app.servicios.boton_panico.routes  import panico_bp
    from app.servicios.control_acceso.routes import control_acceso_bp
    from app.contabilidad                   import register_contabilidad_blueprints

    app.register_blueprint(auth_bp)
    app.register_blueprint(recuperacion_bp)
    app.register_blueprint(slug_bp)
    register_config_blueprints(app)
    app.register_blueprint(servicios_bp)
    app.register_blueprint(servicios_admin_bp)
    app.register_blueprint(directorio_bp)
    app.register_blueprint(panico_bp)
    app.register_blueprint(control_acceso_bp)
    register_contabilidad_blueprints(app)

    app.logger.info("Blueprints registrados: auth, recuperacion, slug, configuracion(x8), contabilidad(x8), directorio, boton_panico, control_acceso")

    # ── Migraciones idempotentes de BD (se ejecutan en cada arranque, son seguras) ──
    try:
        from app.configuracion.roles.model import RolModel
        RolModel._parchar_puede_crear()
        RolModel._marcar_roles_sistema()
        n = RolModel.migrar_asociaciones_ids_a_nombres()
        if n:
            app.logger.info("Migración: %d asociacion(es) corregidas (rol_asignado ID->nombre)", n)
        # Renombrar ImplementadorAriana → ImplementadorNidus (idempotente)
        _r = db["roles"].find_one({"nombre": "ImplementadorAriana"})
        if _r:
            db["roles"].update_one({"_id": _r["_id"]}, {"$set": {"nombre": "ImplementadorNidus", "es_sistema": True}})
            db["asociaciones"].update_many({"rol_asignado": "ImplementadorAriana"}, {"$set": {"rol_asignado": "ImplementadorNidus"}})
            db["sesiones"].update_many({"rol": "ImplementadorAriana"}, {"$set": {"rol": "ImplementadorNidus"}})
            app.logger.info("Migración: ImplementadorAriana → ImplementadorNidus completada")
    except Exception as _e:
        app.logger.warning("Migración roles: %s", _e)

    try:
        from app.servicios.directorio.model import inicializar_plantillas_globales
        inicializar_plantillas_globales()
        # Migración: agregar bloque RESIDENTES a todas las empresas que no lo tengan
        _n = db["directorio_config"].update_many(
            {"bloques.codigo": {"$ne": "RESIDENTES"}},
            {"$push": {"bloques": {
                "codigo": "RESIDENTES", "nombre": "Residentes", "emoji": "🏠",
                "orden": 6, "activo": True, "es_predeterminado": True,
            }}}
        )
        if _n.modified_count:
            app.logger.info("Migración: bloque RESIDENTES agregado a %d empresa(s)", _n.modified_count)
    except Exception as _e:
        app.logger.warning("Inicialización directorio_bloques: %s", _e)

    # ── Catálogo: módulo "Control de Acceso" (ADITIVO — no toca otros datos) ──
    try:
        from datetime import datetime as _dt
        db["servicios"].update_one(
            {"codigo": "control_acceso"},
            {"$setOnInsert": {
                "nombre":      "Control de Acceso",
                "codigo":      "control_acceso",
                "descripcion": "Portería: credenciales (QR/PIN), coacción y citofonía",
                "icono":       "🛂",
                "orden":       50,
                "activo":      True,
                "creado_en":   _dt.utcnow(),
                "creado_por":  "sistema",
            }},
            upsert=True,
        )
        db["access_credentials"].create_index([("conjunto_id", 1), ("codigo", 1)])
        db["access_logs"].create_index([("conjunto_id", 1), ("creado_en", -1)])
    except Exception as _e:
        app.logger.warning("Inicialización control_acceso: %s", _e)

    # ── Twilio Webhooks (recibe estados en tiempo real) ──
    # El poller ya no es necesario — Twilio enviará webhooks automáticamente
    # cuando cambien los estados de SMS, WhatsApp o Llamadas
    # Ver: POST /servicios/boton_panico/webhook/twilio-status

    # ── SLA de contratistas (hilo daemon cada 30 min) ──
    try:
        from app.servicios.control_acceso.sla_worker import iniciar_sla_worker
        iniciar_sla_worker()
        app.logger.info("SLA worker de contratistas iniciado")
    except Exception as _e:
        app.logger.warning("SLA worker no pudo iniciar: %s", _e)

    # ── Cloudinary (inicializar configuración) ──
    try:
        import cloudinary
        cloudinary.config(
            cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
            api_key=os.environ.get("CLOUDINARY_API_KEY", ""),
            api_secret=os.environ.get("CLOUDINARY_API_SECRET", ""),
            secure=True,
        )
        app.logger.info("Cloudinary configurado (cloud=%s)", os.environ.get("CLOUDINARY_CLOUD_NAME", "N/A"))
    except Exception as _e:
        app.logger.warning("Cloudinary no configurado: %s", _e)

    return app
