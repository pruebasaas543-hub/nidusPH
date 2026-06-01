"""
app/servicios/directorio/controller.py
Lógica de negocio para el Directorio de Contactos.
"""

import base64
from app.servicios.directorio.model import ContactoModel, DirectorioConfigModel
from app.configuracion.utils import email_ok

MAX_FOTO_BYTES = 3 * 1024 * 1024


def _foto_desde_file(file_storage):
    """Convierte un FileStorage a (data_b64, mimetype) o (None, None)."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None, None
    raw = file_storage.read()
    if not raw:
        return None, None
    if len(raw) > MAX_FOTO_BYTES:
        return False, "La foto no puede superar 3 MB"
    return base64.b64encode(raw).decode("utf-8"), (file_storage.mimetype or "image/jpeg")


class ContactoController:

    CARGO_REQUERIDO = {"ADMIN", "LOGISTICA"}

    @staticmethod
    def _validar(datos: dict, empresa_id: str = None):
        if not datos.get("nombre", "").strip():
            return False, "El nombre del contacto es obligatorio"
        bloque = datos.get("bloque", "").upper().strip()
        codigos = DirectorioConfigModel.codigos_activos(empresa_id) if empresa_id else set()
        if not codigos:
            from app.servicios.directorio.model import BLOQUES_VALIDOS
            codigos = BLOQUES_VALIDOS
        if bloque not in codigos:
            return False, f"Bloque inválido. Opciones: {', '.join(sorted(codigos))}"
        if bloque in ContactoController.CARGO_REQUERIDO and not datos.get("cargo_titulo", "").strip():
            return False, f"El cargo es obligatorio para el bloque {bloque}"
        correo = datos.get("correo", "").strip()
        if correo and not email_ok(correo):
            return False, "El correo electrónico no tiene formato válido"
        telefonos = datos.get("telefonos", [])
        if not isinstance(telefonos, list) or not telefonos:
            return False, "Debe ingresar al menos un teléfono"
        for t in telefonos:
            if not isinstance(t, dict) or not t.get("numero", "").strip():
                return False, "Cada teléfono debe tener al menos el número"
        return True, None

    @staticmethod
    def crear(datos: dict, empresa_id: str, creado_por: str, foto_file=None):
        ok_val, err_val = ContactoController._validar(datos, empresa_id)
        if not ok_val:
            return False, err_val
        bloque = datos.get("bloque", "").upper().strip()
        limite = DirectorioConfigModel.obtener_limites(empresa_id).get(bloque)
        if limite:
            count = ContactoModel.contar_por_bloque(empresa_id, bloque)
            if count >= limite:
                return False, f"Límite de {limite} contacto(s) alcanzado para el bloque {bloque}"
        if foto_file:
            foto_data, foto_mime = _foto_desde_file(foto_file)
            if foto_data is False:
                return False, foto_mime
            datos["foto_data"]     = foto_data
            datos["foto_mimetype"] = foto_mime
        _id = ContactoModel.crear(datos, empresa_id, creado_por)
        return True, _id

    @staticmethod
    def listar(empresa_id: str, solo_activos: bool = True, campo_visibilidad: str = None):
        try:
            return True, ContactoModel.listar_por_empresa(empresa_id, solo_activos, campo_visibilidad)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def obtener(contacto_id: str, empresa_id: str):
        doc = ContactoModel.obtener(contacto_id, empresa_id)
        if not doc:
            return False, "Contacto no encontrado"
        return True, doc

    @staticmethod
    def actualizar(contacto_id: str, empresa_id: str, datos: dict, foto_file=None):
        doc = ContactoModel.obtener(contacto_id, empresa_id)
        if not doc:
            return False, "Contacto no encontrado"
        ok_val, err_val = ContactoController._validar(datos, empresa_id)
        if not ok_val:
            return False, err_val
        if foto_file:
            foto_data, foto_mime = _foto_desde_file(foto_file)
            if foto_data is False:
                return False, foto_mime
            if foto_data:
                datos["foto_data"]     = foto_data
                datos["foto_mimetype"] = foto_mime
        ContactoModel.actualizar(contacto_id, empresa_id, datos)
        return True, "Contacto actualizado correctamente"

    @staticmethod
    def eliminar(contacto_id: str, empresa_id: str):
        doc = ContactoModel.obtener(contacto_id, empresa_id)
        if not doc:
            return False, "Contacto no encontrado"
        ContactoModel.eliminar(contacto_id, empresa_id)
        return True, "Contacto eliminado"
