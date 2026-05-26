"""
app/configuracion/directorio/controller.py
"""

from app.configuracion.directorio.model import DirectorioModel, BLOQUES


class DirectorioController:

    @staticmethod
    def listar(propiedad_id: str, bloque: str = None):
        if not propiedad_id:
            return False, "ID de empresa requerido"
        try:
            data = DirectorioModel.listar(propiedad_id, bloque)
            return True, data
        except Exception as e:
            return False, str(e)

    @staticmethod
    def crear(propiedad_id: str, datos: dict, archivo, creado_por: str):
        if not propiedad_id:
            return False, "ID de empresa requerido"
        nombre = (datos.get("nombre") or "").strip()
        bloque = (datos.get("bloque") or "").strip().upper()
        telefonos = [t.strip() for t in datos.get("telefonos", []) if t.strip()]

        if not nombre:
            return False, "El nombre es requerido"
        if bloque not in BLOQUES:
            return False, f"Bloque inválido. Debe ser: {', '.join(BLOQUES)}"
        if not telefonos:
            return False, "Debe ingresar al menos un teléfono"

        try:
            contacto_id = DirectorioModel.crear(propiedad_id, datos, archivo, creado_por)
            return True, {"contacto_id": contacto_id, "mensaje": "Contacto creado correctamente"}
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Error al guardar: {str(e)}"

    @staticmethod
    def actualizar(contacto_id: str, datos: dict, archivo):
        if not contacto_id:
            return False, "ID de contacto requerido"
        nombre = (datos.get("nombre") or "").strip()
        bloque = (datos.get("bloque") or "").strip().upper()
        telefonos = [t.strip() for t in datos.get("telefonos", []) if t.strip()]

        if not nombre:
            return False, "El nombre es requerido"
        if bloque not in BLOQUES:
            return False, f"Bloque inválido. Debe ser: {', '.join(BLOQUES)}"
        if not telefonos:
            return False, "Debe ingresar al menos un teléfono"

        if not DirectorioModel.obtener(contacto_id):
            return False, "Contacto no encontrado"

        try:
            datos["bloque"] = bloque
            datos["telefonos"] = telefonos
            DirectorioModel.actualizar(contacto_id, datos, archivo)
            return True, "Contacto actualizado correctamente"
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Error al actualizar: {str(e)}"

    @staticmethod
    def eliminar(contacto_id: str):
        if not contacto_id:
            return False, "ID de contacto requerido"
        if not DirectorioModel.obtener(contacto_id):
            return False, "Contacto no encontrado"
        DirectorioModel.eliminar(contacto_id)
        return True, "Contacto eliminado correctamente"

    @staticmethod
    def obtener_foto(contacto_id: str):
        foto = DirectorioModel.obtener_foto(contacto_id)
        if not foto:
            return False, "Sin foto"
        return True, foto
