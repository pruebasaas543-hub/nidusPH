"""
app/servicios/directorio/controller.py
Lógica de negocio para Cargos y Funcionarios del Directorio.
"""

import json
from app.servicios.directorio.model import CargoModel, FuncionarioModel
from app.configuracion.utils import email_ok


CATEGORIAS_VALIDAS = {"Administración", "Seguridad", "Órganos de Control"}


# ── CARGOS ────────────────────────────────────────────────────────────────

class CargoController:

    @staticmethod
    def crear(datos: dict, creado_por: str):
        nombre = datos.get("nombre", "").strip()
        if not nombre:
            return False, "El nombre del cargo es obligatorio"
        if len(nombre) > 80:
            return False, "El nombre del cargo no puede superar 80 caracteres"
        categoria = datos.get("categoria", "").strip()
        if categoria not in CATEGORIAS_VALIDAS:
            return False, f"Categoría inválida. Opciones: {', '.join(sorted(CATEGORIAS_VALIDAS))}"
        if CargoModel.obtener_por_nombre(nombre):
            return False, f"Ya existe un cargo con el nombre '{nombre}'"
        datos["requiere_horario"] = datos.get("requiere_horario") in (True, "true", "True", "1", 1)
        _id = CargoModel.crear(datos, creado_por)
        return True, _id

    @staticmethod
    def listar(solo_activos: bool = True):
        try:
            return True, CargoModel.listar(solo_activos)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def obtener(cargo_id: str):
        doc = CargoModel.obtener(cargo_id)
        if not doc:
            return False, "Cargo no encontrado"
        return True, doc

    @staticmethod
    def actualizar(cargo_id: str, datos: dict):
        nombre = datos.get("nombre", "").strip()
        if not nombre:
            return False, "El nombre del cargo es obligatorio"
        categoria = datos.get("categoria", "").strip()
        if categoria not in CATEGORIAS_VALIDAS:
            return False, f"Categoría inválida. Opciones: {', '.join(sorted(CATEGORIAS_VALIDAS))}"
        existente = CargoModel.obtener_por_nombre(nombre)
        if existente and str(existente["_id"]) != cargo_id:
            return False, f"Ya existe otro cargo con el nombre '{nombre}'"
        datos["requiere_horario"] = datos.get("requiere_horario") in (True, "true", "True", "1", 1)
        CargoModel.actualizar(cargo_id, datos)
        return True, "Cargo actualizado correctamente"

    @staticmethod
    def cambiar_estado(cargo_id: str, activo: bool):
        if not activo and CargoModel.en_uso(cargo_id):
            return False, "No se puede inactivar: hay funcionarios activos con este cargo"
        CargoModel.cambiar_estado(cargo_id, activo)
        return True, "Estado del cargo actualizado"


# ── FUNCIONARIOS ──────────────────────────────────────────────────────────

def _horario_raw(datos: dict) -> dict:
    """Extrae el sub-objeto horario del payload (soporta string JSON o dict)."""
    raw = datos.get("horario", {})
    if isinstance(raw, str):
        try:    return json.loads(raw)
        except: return {}
    return raw if isinstance(raw, dict) else {}


class FuncionarioController:

    @staticmethod
    def crear(datos: dict, creado_por: str, ip: str):
        if not datos.get("nombres", "").strip():
            return False, "El nombre es obligatorio"
        if not datos.get("apellidos", "").strip():
            return False, "Los apellidos son obligatorios"
        if not datos.get("cargo_id", "").strip():
            return False, "Debe seleccionar un cargo"
        if not datos.get("fecha_inicio", "").strip():
            return False, "La fecha de inicio es obligatoria"
        email = datos.get("email", "").strip()
        if email and not email_ok(email):
            return False, "El correo electrónico no tiene formato válido"

        # RN-DIR-01: habeas data obligatorio en creación
        if datos.get("habeas_data") not in (True, "true", "True", "1", 1):
            return False, "Debe aceptar la autorización de tratamiento de datos personales"

        cargo = CargoModel.obtener(datos["cargo_id"])
        if not cargo:
            return False, "El cargo seleccionado no existe"
        datos["cargo_nombre"]    = cargo.get("nombre", "")
        datos["cargo_categoria"] = cargo.get("categoria", "")

        if cargo.get("requiere_horario"):
            h = _horario_raw(datos)
            if not h.get("hora_entrada", "").strip():
                return False, "La hora de entrada es obligatoria para este cargo"
            if not h.get("hora_salida", "").strip():
                return False, "La hora de salida es obligatoria para este cargo"

        _id = FuncionarioModel.crear(datos, creado_por, ip)
        return True, _id

    @staticmethod
    def listar(solo_activos: bool = True):
        try:
            return True, FuncionarioModel.listar(solo_activos)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def obtener(funcionario_id: str):
        doc = FuncionarioModel.obtener(funcionario_id)
        if not doc:
            return False, "Funcionario no encontrado"
        return True, doc

    @staticmethod
    def actualizar(funcionario_id: str, datos: dict):
        doc = FuncionarioModel.obtener(funcionario_id)
        if not doc:
            return False, "Funcionario no encontrado"
        if not doc.get("activo"):
            return False, "No se puede editar un funcionario inactivo"
        email = datos.get("email", "").strip()
        if email and not email_ok(email):
            return False, "El correo electrónico no tiene formato válido"
        cargo = CargoModel.obtener(datos.get("cargo_id", ""))
        if not cargo:
            return False, "El cargo seleccionado no existe"
        datos["cargo_nombre"]    = cargo.get("nombre", "")
        datos["cargo_categoria"] = cargo.get("categoria", "")
        if cargo.get("requiere_horario"):
            h = _horario_raw(datos)
            if not h.get("hora_entrada", "").strip():
                return False, "La hora de entrada es obligatoria para este cargo"
            if not h.get("hora_salida", "").strip():
                return False, "La hora de salida es obligatoria para este cargo"
        FuncionarioModel.actualizar(funcionario_id, datos)
        return True, "Funcionario actualizado correctamente"

    @staticmethod
    def inactivar(funcionario_id: str, fecha_fin: str, inactivado_por: str):
        """RN-DIR-03: inactivación histórica."""
        doc = FuncionarioModel.obtener(funcionario_id)
        if not doc:
            return False, "Funcionario no encontrado"
        if not doc.get("activo"):
            return False, "El funcionario ya está inactivo"
        if not fecha_fin or not fecha_fin.strip():
            return False, "La fecha de fin de labores es obligatoria"
        FuncionarioModel.inactivar(funcionario_id, fecha_fin.strip(), inactivado_por)
        return True, "Funcionario inactivado. El registro se mantiene en el histórico"

    @staticmethod
    def reactivar(funcionario_id: str):
        doc = FuncionarioModel.obtener(funcionario_id)
        if not doc:
            return False, "Funcionario no encontrado"
        if doc.get("activo"):
            return False, "El funcionario ya está activo"
        FuncionarioModel.reactivar(funcionario_id)
        return True, "Funcionario reactivado correctamente"
