"""
app/configuracion/empresas/controller.py
"""

from app.configuracion.empresas.model import EmpresaModel
from app.configuracion.catalogos.model import CatalogoModel
from app.configuracion.utils import email_ok, color_ok, imagen_ok


class EmpresaController:

    @staticmethod
    def obtener_catalogos():
        return True, {
            "departamentos":    CatalogoModel.departamentos(),
            "tipos_ph":         CatalogoModel.tipos_ph(),
            "planes_saas":      CatalogoModel.planes_saas(),
            "mapa_municipios":  CatalogoModel.mapa_municipios(),
            "estados_contrato": CatalogoModel.estados_contrato(),
        }

    @staticmethod
    def municipios_por_depto(nombre_depto: str):
        if not nombre_depto:
            return False, "Nombre de departamento requerido"
        return True, CatalogoModel.municipios(nombre_depto)

    @staticmethod
    def listar():
        return True, EmpresaModel.listar(solo_activas=False)

    @staticmethod
    def crear(datos: dict, archivos: dict, creado_por: str):
        nit          = datos.get("nit", "").strip()
        razon_social = datos.get("razon_social", "").strip()
        email        = datos.get("email", "").strip()
        slug         = datos.get("slug", "").strip().lower().replace(" ", "-")

        if not nit:          return False, "El NIT es obligatorio"
        if not razon_social: return False, "La Razón Social es obligatoria"
        if not email or not email_ok(email):
            return False, "El correo de contacto no es válido"

        if not slug:
            slug = razon_social.lower().replace(" ", "-")
            datos["slug"] = slug

        if EmpresaModel.buscar_por_nit(nit):
            return False, f"Ya existe una empresa con NIT {nit}"
        if EmpresaModel.buscar_por_slug(slug):
            return False, f"El slug '{slug}' ya está en uso"

        for campo, etiqueta in [("logo","Logo"),("carousel_1","Carrusel 1"),
                                 ("carousel_2","Carrusel 2"),("carousel_3","Carrusel 3")]:
            ok_img, msg = imagen_ok(archivos.get(campo), etiqueta)
            if not ok_img: return False, msg

        empresa_id = EmpresaModel.crear(datos, archivos, creado_por)
        return True, {"empresa_id": empresa_id, "mensaje": "Empresa registrada correctamente"}

    @staticmethod
    def editar(empresa_id: str, datos: dict, archivos=None):
        empresa = EmpresaModel.buscar_por_id(empresa_id)
        if not empresa: return False, "Empresa no encontrada"

        email = datos.get("email", "").strip()
        if email and not email_ok(email):
            return False, "El correo no es válido"

        datos.pop("slug", None)

        if archivos:
            for campo, etiqueta in [("logo","Logo"),("carousel_1","Carrusel 1"),
                                     ("carousel_2","Carrusel 2"),("carousel_3","Carrusel 3")]:
                ok_img, msg = imagen_ok(archivos.get(campo), etiqueta)
                if not ok_img: return False, msg

        EmpresaModel.actualizar(empresa_id, datos, archivos)
        return True, "Empresa actualizada correctamente"

    @staticmethod
    def cambiar_estado(empresa_id: str, activo: bool, estado_contrato_id: str = None, motivo: str = None):
        if not EmpresaModel.buscar_por_id(empresa_id):
            return False, "Empresa no encontrada"
        EmpresaModel.cambiar_estado(empresa_id, activo, estado_contrato_id, motivo)
        return True, f"Empresa {'activada' if activo else 'desactivada'} correctamente"

    @staticmethod
    def obtener_imagen(empresa_id: str, campo: str):
        if campo not in EmpresaModel.CAMPOS_IMAGEN:
            return False, "Campo no válido"
        img = EmpresaModel.obtener_imagen(empresa_id, campo)
        if not img: return False, "Imagen no encontrada"
        return True, img
