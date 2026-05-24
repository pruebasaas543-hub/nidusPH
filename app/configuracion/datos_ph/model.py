"""
app/configuracion/datos_ph/model.py
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col(): return db["datos_generales_ph"]


class DatosGeneralesPHModel:

    @staticmethod
    def _build_parqueaderos(datos: dict) -> dict:
        def slot(tipo, cat):
            return {"cantidad": int(datos.get(f"cant_parq_{tipo}_{cat}", 0) or 0)}
        return {
            "Carros": {
                "Comunales":  slot("com",  "carros"),
                "Propios":    slot("prop", "carros"),
                "Visitantes": slot("vis",  "carros"),
            },
            "Motos": {
                "Comunales":  slot("com",  "motos"),
                "Propios":    slot("prop", "motos"),
                "Visitantes": slot("vis",  "motos"),
            },
        }

    @staticmethod
    def _build_info_tributaria(datos: dict) -> dict:
        it = datos.get("info_tributaria", {})
        if isinstance(it, str):
            import json as _json
            try:    it = _json.loads(it)
            except: it = {}
        if not isinstance(it, dict):
            it = {}
        def _s(k): return str(it.get(k, "") or "").strip()
        return {
            "tipo_doc":                       _s("tipo_doc"),
            "numero_identificacion":          _s("numero_identificacion"),
            "digito_verificacion":            _s("digito_verificacion"),
            "razon_social":                   _s("razon_social"),
            "nombre_comercial":               _s("nombre_comercial"),
            "tipo_organizacion":              _s("tipo_organizacion"),
            "direccion":                      _s("direccion"),
            "codigo_postal":                  _s("codigo_postal"),
            "telefono":                       _s("telefono"),
            "pais":                           _s("pais") or "Colombia",
            "departamento":                   _s("departamento"),
            "ciudad":                         _s("ciudad"),
            "correo_facturacion_electronica": _s("correo_facturacion_electronica"),
            "sitio_web":                      _s("sitio_web"),
            "tributos_aplicables":            it.get("tributos_aplicables", [])
                                              if isinstance(it.get("tributos_aplicables"), list) else [],
        }

    @staticmethod
    def _build_info_contractual(datos: dict) -> dict:
        def _f(k): return str(datos.get(k, "") or "").strip()
        def _n(k):
            raw = str(datos.get(k, 0) or 0)
            if "," in raw and "." in raw:
                raw = raw.replace(".", "").replace(",", ".")
            elif "," in raw:
                raw = raw.replace(",", ".")
            try:    return float(raw)
            except: return 0.0
        return {
            "numero_contrato":             _f("num_contrato"),
            "fecha_inicio":                _f("contrato_fecha_inicio"),
            "meses_contratados":           int(datos.get("meses_contratados", 0) or 0),
            "fecha_finalizacion":          _f("contrato_fecha_fin"),
            "plan_contratado":             _f("plan_contratado"),
            "correo_facturacion":          _f("correo_facturacion"),
            "cant_unidades":               int(datos.get("cant_unidades", 0) or 0),
            "valor_copropiedad":           _n("valor_copropiedad"),
            "valor_facturacion_mensual":   _n("valor_facturacion_mensual"),
            "dia_generacion_facturacion":  _f("dia_generacion_facturacion"),
            "hora_generacion_facturacion": _f("hora_generacion_facturacion"),
        }

    @staticmethod
    def crear(empresa_id: str, datos: dict, creado_por: str) -> str:
        doc = {
            "empresa_id":         ObjectId(empresa_id),
            "info_contractual":   DatosGeneralesPHModel._build_info_contractual(datos),
            "info_tributaria":    DatosGeneralesPHModel._build_info_tributaria(datos),
            "regimen_tributario": datos.get("regimen_tributario", []) if isinstance(datos.get("regimen_tributario"), list) else [],
            "obligaciones_rut":   datos.get("obligaciones_rut", []) if isinstance(datos.get("obligaciones_rut"), list) else [],
            "ciiu":               datos.get("ciiu", []) if isinstance(datos.get("ciiu"), list) else [],
            "estrato":            str(datos.get("estrato", "") or "").strip(),
            "parqueaderos":       DatosGeneralesPHModel._build_parqueaderos(datos),
            "correo_admin":           str(datos.get("correo_admin", "") or "").strip(),
            "tel_admin":              str(datos.get("tel_admin", "") or "").strip(),
            "cel_admin":              str(datos.get("cel_admin", "") or "").strip(),
            "dias_horarios":          datos.get("dias_horarios", {}),
            "representante_legal":    datos.get("representante_legal", {}),
            "representante_suplente": datos.get("representante_suplente", {}),
            "creado_en":              datetime.utcnow(),
            "creado_por":             creado_por,
            "actualizado_en":         None,
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def _campos_update(datos: dict) -> dict:
        return {
            "info_contractual":   DatosGeneralesPHModel._build_info_contractual(datos),
            "info_tributaria":    DatosGeneralesPHModel._build_info_tributaria(datos),
            "regimen_tributario": datos.get("regimen_tributario", []) if isinstance(datos.get("regimen_tributario"), list) else [],
            "obligaciones_rut":   datos.get("obligaciones_rut", []) if isinstance(datos.get("obligaciones_rut"), list) else [],
            "ciiu":               datos.get("ciiu", []) if isinstance(datos.get("ciiu"), list) else [],
            "estrato":            str(datos.get("estrato", "") or "").strip(),
            "parqueaderos":       DatosGeneralesPHModel._build_parqueaderos(datos),
            "correo_admin":           str(datos.get("correo_admin", "") or "").strip(),
            "tel_admin":              str(datos.get("tel_admin", "") or "").strip(),
            "cel_admin":              str(datos.get("cel_admin", "") or "").strip(),
            "dias_horarios":          datos.get("dias_horarios", {}),
            "representante_legal":    datos.get("representante_legal", {}),
            "representante_suplente": datos.get("representante_suplente", {}),
            "actualizado_en":         datetime.utcnow(),
        }

    @staticmethod
    def actualizar(empresa_id: str, datos: dict):
        _col().update_one(
            {"empresa_id": ObjectId(empresa_id)},
            {
                "$set":   DatosGeneralesPHModel._campos_update(datos),
                "$unset": {"cant_unidades": "", "estado_contrato": "", "dia_pago": ""},
            }
        )

    @staticmethod
    def obtener(empresa_id: str):
        return _col().find_one({"empresa_id": ObjectId(empresa_id)})

    @staticmethod
    def listar() -> list:
        return list(_col().find())

    @staticmethod
    def eliminar(config_id: str):
        _col().delete_one({"_id": ObjectId(config_id)})
