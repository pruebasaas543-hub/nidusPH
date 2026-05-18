"""
app/slug/model.py
─────────────────
Módulo de portal público por empresa. Cada empresa tiene un slug único
que se usa como subdirectorio:  https://nidus.app/<slug>/

Lee directamente de la colección 'empresas' sin crear duplicados.
El slug es la llave pública; el _id de la empresa es la llave interna.
"""

from app import db


def _col(): return db["empresas"]


class SlugModel:

    CAMPOS_BRANDING = {
        "nit", "digito_verificacion", "razon_social", "slug",
        "color_topbar", "color_panel_izq",
        "logo_data", "logo_mimetype",
        "carousel_1_data", "carousel_1_mimetype",
        "carousel_2_data", "carousel_2_mimetype",
        "carousel_3_data", "carousel_3_mimetype",
    }

    @staticmethod
    def buscar_por_slug(slug: str):
        """Retorna la empresa con sus campos de branding, sin datos sensibles."""
        if not slug:
            return None
        doc = _col().find_one(
            {"slug": slug.strip().lower(), "activo": True},
            {c: 1 for c in SlugModel.CAMPOS_BRANDING} | {"_id": 1, "activo": 1}
        )
        return doc

    @staticmethod
    def obtener_imagen(slug: str, campo: str):
        """Sirve imágenes base64 guardadas en empresas.{campo}_data."""
        doc = _col().find_one(
            {"slug": slug.strip().lower(), "activo": True},
            {f"{campo}_data": 1, f"{campo}_mimetype": 1}
        )
        if not doc or not doc.get(f"{campo}_data"):
            return None
        return {"data": doc[f"{campo}_data"], "mimetype": doc[f"{campo}_mimetype"]}
