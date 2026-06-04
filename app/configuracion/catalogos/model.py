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
        docs = list(_col("estados_contrato").find({}, {"codigo": 1, "nombre": 1}).sort("nombre", 1))
        if not docs:
            return [
                {"id": None, "codigo": "ACTIVO",     "nombre": "Activo"},
                {"id": None, "codigo": "VENCIDO",    "nombre": "Vencido"},
                {"id": None, "codigo": "SUSPENDIDO", "nombre": "Suspendido"},
                {"id": None, "codigo": "CANCELADO",  "nombre": "Cancelado"},
            ]
        return [{"id": str(d["_id"]), "codigo": str(d.get("codigo") or "").upper(), "nombre": d.get("nombre","")} for d in docs]

    @staticmethod
    def obligaciones_rut() -> list:
        docs = list(_col("obligaciones_rut").find({}, {"_id": 1, "codigo": 1, "nombre": 1}).sort("nombre", 1))
        return [{"id": str(d["_id"]), "codigo": d.get("codigo", ""), "nombre": d.get("nombre", "")} for d in docs]

    @staticmethod
    def tipo_identificador_fiscal() -> list:
        docs = list(
            _col("tipo_identificador_fiscal")
            .find({}, {"id_sigla": 1, "nombre": 1})
            .sort("nombre", 1)
        )
        if docs:
            return [{"id": str(d["_id"]), "codigo": d["id_sigla"], "nombre": d["nombre"]}
                    for d in docs if d.get("id_sigla")]
        # Fallback: leer de TIPOS_DOCUMENTO en memoria (ya cargado desde MongoDB al iniciar)
        from app.autenticacion.model import TIPOS_DOCUMENTO
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

    @staticmethod
    def _like_regex(texto: str) -> str:
        """
        Convierte un texto a un patrón regex insensible a tildes y mayúsculas.
        Cada vocal/ñ se convierte en una clase que acepta ambas versiones.
        """
        import re as _re
        import unicodedata

        # Normalizar: quitar tildes para trabajar sobre base limpia
        base = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode("ascii").strip()

        _map = {
            "a": "[aáàâä]", "e": "[eéèêë]", "i": "[iíìîï]",
            "o": "[oóòôö]", "u": "[uúùûü]", "n": "[nñ]",
        }
        resultado = ""
        for c in base:
            cl = c.lower()
            if cl in _map:
                resultado += _map[cl]
            elif c in r"\.^$*+?{}[]|()" :
                resultado += _re.escape(c)
            else:
                resultado += c
        return resultado

    @staticmethod
    def _limpiar_depto(nombre: str) -> str:
        """Quita sufijos que difieren entre colecciones antes de la búsqueda."""
        for parte in [
            "Archipiélago de ", "Archipielago de ",
            " D.C.", " D.C", " D,C,",
            ", Providencia y Santa Catalina",
            " y Providencia y Santa Catalina",
            " y Santa Catalina",
            " y Providencia",
        ]:
            nombre = nombre.replace(parte, "")
        return nombre.strip()

    @staticmethod
    def codigos_postales(departamento: str = "", ciudad: str = "") -> list:
        filtro = {}
        if departamento:
            kw = CatalogoModel._like_regex(CatalogoModel._limpiar_depto(departamento))
            filtro["Departamento"] = {"$regex": kw, "$options": "i"}
        ciudad = CatalogoModel._limpiar_depto(ciudad.strip())
        if ciudad and not ciudad.isdigit():
            filtro["Ciudad"] = {"$regex": CatalogoModel._like_regex(ciudad), "$options": "i"}
        docs = list(
            _col("codigospostales")
            .find(filtro)
            .sort("Código Postal", 1)
            .limit(100)
        )
        return [
            {
                "codigo":       str(d.get("Código Postal", "")),
                "ciudad":       d.get("Ciudad", ""),
                "departamento": d.get("Departamento", ""),
            }
            for d in docs
            if d.get("Código Postal")
        ]

