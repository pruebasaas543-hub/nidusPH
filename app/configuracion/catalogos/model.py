"""
app/configuracion/catalogos/model.py
─────────────────────────────────────
Catálogos de solo-lectura usados por varios módulos.
Centralizar aquí evita que cada módulo acceda a las mismas colecciones por separado.
"""

from app import db


def _col(nombre): return db[nombre]


class CatalogoModel:

    @staticmethod
    def departamentos() -> list:
        docs = list(
            _col("geografia")
            .find({}, {"_id": 0, "departamento": 1, "codigo_depto": 1})
            .sort("departamento", 1)
        )
        return [{"departamento": d["departamento"], "codigo_dane": d.get("codigo_depto", "")} for d in docs]

    @staticmethod
    def municipios(nombre_depto: str) -> list:
        doc = _col("geografia").find_one(
            {"departamento": nombre_depto}, {"_id": 0, "municipios": 1}
        )
        return sorted(doc.get("municipios", []), key=lambda m: m["nombre"]) if doc else []

    @staticmethod
    def mapa_municipios() -> dict:
        """Retorna {codigo: nombre} para todos los municipios de todos los departamentos."""
        docs = list(_col("geografia").find({}, {"_id": 0, "municipios": 1}))
        result = {}
        for doc in docs:
            for m in doc.get("municipios", []):
                codigo = m.get("codigo") or m.get("codigo_dane", "")
                nombre = m.get("nombre", "")
                if codigo and nombre:
                    result[str(codigo)] = nombre
        return result

    @staticmethod
    def tipos_ph() -> list:
        docs = list(_col("tipos_ph").find({}, {"_id": 1, "nombre": 1}).sort("nombre", 1))
        if not docs:
            return [
                {"_id": "propiedad_horizontal", "nombre": "Propiedad Horizontal"},
                {"_id": "empresa_inmobiliaria",  "nombre": "Empresa Inmobiliaria"},
                {"_id": "constructora",          "nombre": "Constructora"},
                {"_id": "otro",                  "nombre": "Otro"},
            ]
        return [{"_id": str(d["_id"]), "nombre": d.get("nombre", str(d["_id"]))} for d in docs]

    @staticmethod
    def planes_saas() -> list:
        from app import db as _db
        estado_doc = _db["estado_planes"].find_one({"nombre": "activo"})
        filtro = {"estado": str(estado_doc["_id"])} if estado_doc else {"estado": "activo"}
        docs = list(_col("planes_saas").find(filtro).sort("orden", 1))
        return [
            {
                "_id":               str(d["_id"]),
                "plan_id":           d.get("plan_id", ""),
                "nombre":            d.get("nombre", ""),
                "descripcion":       d.get("descripcion", ""),
                "modulos_incluidos": d.get("modulos_incluidos", []),
                "valor_copropiedad": d.get("precio", {}).get("valor_copropiedad", 0),
            }
            for d in docs
        ]

    @staticmethod
    def responsabilidades_dian() -> list:
        docs = list(
            _col("responsabilidades_dian")
            .find({}, {"_id": 1, "codigo": 1, "nombre": 1, "descripcion": 1})
            .sort("codigo", 1)
        )
        return [
            {
                "id":          str(d["_id"]),
                "codigo":      d.get("codigo", ""),
                "nombre":      d.get("nombre", d.get("descripcion", "")),
                "descripcion": d.get("descripcion", ""),
            }
            for d in docs
        ]

    @staticmethod
    def actividades_ciiu() -> list:
        docs = list(
            _col("actividades_ciiu")
            .find({}, {"_id": 1, "codigo": 1, "nombre": 1})
        )
        return [
            {"id": str(d["_id"]), "codigo": d.get("codigo", ""), "nombre": d.get("nombre", "")}
            for d in docs
        ]

    @staticmethod
    def estratos() -> list:
        docs = list(
            _col("estratos")
            .find({}, {"_id": 1, "nivel": 1})
            .sort("nivel", 1)
        )
        return [
            {
                "id":     str(d["_id"]),
                "numero": d.get("nivel", ""),
            }
            for d in docs
        ]

    @staticmethod
    def estados_contrato() -> list:
        docs = list(_col("estados_contrato").find({}, {"_id": 0, "codigo": 1, "nombre": 1}).sort("nombre", 1))
        if not docs:
            return [
                {"codigo": "ACTIVO",     "nombre": "Activo"},
                {"codigo": "VENCIDO",    "nombre": "Vencido"},
                {"codigo": "SUSPENDIDO", "nombre": "Suspendido"},
                {"codigo": "CANCELADO",  "nombre": "Cancelado"},
            ]
        return docs

    @staticmethod
    def obligaciones_rut() -> list:
        docs = list(_col("obligaciones_rut").find({}, {"_id": 1, "codigo": 1, "nombre": 1}).sort("nombre", 1))
        return [{"id": str(d["_id"]), "codigo": d.get("codigo", ""), "nombre": d.get("nombre", "")} for d in docs]

    @staticmethod
    def tipo_identificador_fiscal() -> list:
        docs = list(
            _col("tipo_identificador_fiscal")
            .find({}, {"_id": 0, "id_sigla": 1, "nombre": 1})
            .sort("nombre", 1)
        )
        if docs:
            return [{"codigo": d["id_sigla"], "nombre": d["nombre"]}
                    for d in docs if d.get("id_sigla")]
        # Fallback: leer de TIPOS_DOCUMENTO en memoria (ya cargado desde MongoDB al iniciar)
        from app.auth.model import TIPOS_DOCUMENTO
        return sorted(
            [{"codigo": sigla, "nombre": info["nombre"]} for sigla, info in TIPOS_DOCUMENTO.items()],
            key=lambda x: x["nombre"]
        )

    @staticmethod
    def tipos_organizacion() -> list:
        docs = list(
            _col("tipos_organizacion")
            .find({}, {"_id": 1, "nombre": 1})
            .sort("nombre", 1)
        )
        return [{"id": str(d["_id"]), "nombre": d.get("nombre", "")} for d in docs]

    @staticmethod
    def tributos() -> list:
        docs = list(
            _col("tributos")
            .find({}, {"_id": 1, "codigo": 1, "nombre": 1})
            .sort("codigo", 1)
        )
        return [
            {"id": str(d["_id"]), "codigo": d.get("codigo", ""), "nombre": d.get("nombre", "")}
            for d in docs
        ]

