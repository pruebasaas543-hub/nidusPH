"""
app/slug/controller.py
"""

from app.slug.model import SlugModel
from app.configuracion.empresas.model import EmpresaModel


class SlugController:

    @staticmethod
    def resolver(slug: str):
        """Retorna (True, empresa_dict) o (False, mensaje)."""
        if not slug:
            return False, "Slug no proporcionado"
        empresa = SlugModel.buscar_por_slug(slug)
        if not empresa:
            return False, "Empresa no encontrada o inactiva"
        return True, empresa

    @staticmethod
    def obtener_imagen(slug: str, campo: str):
        campos_validos = ["logo", "carousel_1", "carousel_2", "carousel_3"]
        if campo not in campos_validos:
            return False, "Campo de imagen no válido"
        img = SlugModel.obtener_imagen(slug, campo)
        if not img:
            return False, "Imagen no encontrada"
        return True, img

    @staticmethod
    def contexto_branding(slug: str) -> dict:
        """
        Retorna un diccionario listo para inyectar en cualquier template
        que quiera aplicar los colores, logo y carrusel de la empresa.
        """
        exito, empresa = SlugController.resolver(slug)
        if not exito:
            return {}
        return {
            "empresa_id":       str(empresa["_id"]),
            "razon_social":     empresa.get("razon_social", ""),
            "color_topbar":     empresa.get("color_topbar",    "#0a1250"),
            "color_panel_izq":  empresa.get("color_panel_izq", "#080e2e"),
            "slug":             empresa.get("slug", ""),
            "tiene_logo":       bool(empresa.get("logo_data")),
            "tiene_carousel_1": bool(empresa.get("carousel_1_data")),
            "tiene_carousel_2": bool(empresa.get("carousel_2_data")),
            "tiene_carousel_3": bool(empresa.get("carousel_3_data")),
        }
