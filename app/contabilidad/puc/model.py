"""
app/contabilidad/puc/model.py
─────────────────────────────
Operaciones MongoDB para cont_puc (Plan Único de Cuentas).
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col():
    return db["cont_puc"]


class PucModel:

    @staticmethod
    def crear(datos: dict) -> str:
        doc = {
            "codigo":               datos["codigo"].strip(),
            "nombre":               datos["nombre"].strip(),
            "naturaleza":           datos.get("naturaleza", "D"),       # D=Débito, C=Crédito
            "nivel":                int(datos.get("nivel", 1)),
            "padre_id":             datos.get("padre_id") or None,
            "tipo":                 datos.get("tipo", "local"),          # local / niif
            "cuenta_niif_id":       datos.get("cuenta_niif_id") or None, # mapeo multilibro
            "exige_tercero":        bool(datos.get("exige_tercero", False)),
            "exige_centro_costos":  bool(datos.get("exige_centro_costos", False)),
            "activa":               True,
            "saldo_inicial":        float(datos.get("saldo_inicial", 0) or 0),
            "creado_en":            datetime.utcnow(),
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def actualizar(cuenta_id: str, datos: dict):
        # RN-PUC-01: codigo es inmutable — se excluye siempre
        campos = {}
        for campo in ("nombre", "naturaleza", "padre_id", "tipo",
                      "cuenta_niif_id", "exige_tercero", "exige_centro_costos",
                      "activa", "saldo_inicial"):
            if campo in datos:
                campos[campo] = datos[campo]
        campos["actualizado_en"] = datetime.utcnow()
        _col().update_one({"_id": ObjectId(cuenta_id)}, {"$set": campos})

    @staticmethod
    def cambiar_estado(cuenta_id: str, activa: bool):
        _col().update_one(
            {"_id": ObjectId(cuenta_id)},
            {"$set": {"activa": activa, "actualizado_en": datetime.utcnow()}}
        )

    @staticmethod
    def eliminar(cuenta_id: str):
        _col().delete_one({"_id": ObjectId(cuenta_id)})

    @staticmethod
    def listar(filtros: dict = None) -> list:
        q = filtros or {}
        return list(_col().find(q).sort("codigo", 1))

    @staticmethod
    def obtener(cuenta_id: str):
        return _col().find_one({"_id": ObjectId(cuenta_id)})

    @staticmethod
    def buscar_por_codigo(codigo: str):
        return _col().find_one({"codigo": codigo.strip()})

    @staticmethod
    def tiene_movimientos(cuenta_id: str) -> bool:
        """RN-PUC-02: bloquea eliminación si tiene asientos O saldo inicial."""
        tiene_asientos = db["cont_asientos"].count_documents({"cuenta_id": cuenta_id}) > 0
        if tiene_asientos:
            return True
        cuenta = _col().find_one({"_id": ObjectId(cuenta_id)}, {"saldo_inicial": 1})
        return bool(cuenta and cuenta.get("saldo_inicial", 0) != 0)

    @staticmethod
    def importar_lote(cuentas: list) -> dict:
        """Importación masiva. Retorna resumen: insertadas, duplicadas, errores."""
        insertadas, duplicadas, errores = 0, 0, []
        for c in cuentas:
            try:
                codigo = str(c.get("codigo", "")).strip()
                if not codigo or not c.get("nombre"):
                    errores.append(f"Fila sin código/nombre: {c}")
                    continue
                if PucModel.buscar_por_codigo(codigo):
                    duplicadas += 1
                    continue
                PucModel.crear(c)
                insertadas += 1
            except Exception as e:
                errores.append(f"Error en {c.get('codigo')}: {str(e)}")
        return {"insertadas": insertadas, "duplicadas": duplicadas, "errores": errores}

    @staticmethod
    def cuentas_niif() -> list:
        """Lista cuentas de tipo niif para el selector de mapeo multilibro."""
        return list(_col().find({"tipo": "niif", "activa": True}, {"_id": 1, "codigo": 1, "nombre": 1}).sort("codigo", 1))
