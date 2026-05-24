"""
app/configuracion/datos_ph/controller.py
"""

import json
from app.configuracion.datos_ph.model import DatosGeneralesPHModel
from app.configuracion.empresas.model import EmpresaModel


class DatosGeneralesPHController:

    @staticmethod
    def _enriquecer(doc):
        from app import db
        from bson import ObjectId as OId
        from app.configuracion.planes.model import PlanModel

        # Enriquecer regimen_tributario (soporta [{tributo_id, base_imponible}] y legado [id])
        if doc.get("regimen_tributario") and isinstance(doc["regimen_tributario"], list):
            col = db["responsabilidades_dian"]
            enriquecido = []
            for item in doc["regimen_tributario"]:
                try:
                    if isinstance(item, dict):
                        raw_id = item.get("tributo_id", "")
                    else:
                        raw_id = item
                    found = col.find_one({"_id": OId(str(raw_id))})
                    if found:
                        entry = {
                            "id":            str(found["_id"]),
                            "codigo":        found.get("codigo", ""),
                            "nombre":        found.get("nombre", found.get("descripcion", "")),
                            "descripcion":   found.get("descripcion", ""),
                        }
                        if isinstance(item, dict):
                            entry["base_imponible"] = item.get("base_imponible", 0)
                        enriquecido.append(entry)
                except Exception:
                    pass
            doc["regimen_tributario_enriquecido"] = enriquecido

        # Enriquecer ciiu
        if doc.get("ciiu") and isinstance(doc["ciiu"], list):
            col = db["actividades_ciiu"]
            enriquecido = []
            for item_id in doc["ciiu"]:
                try:
                    item = col.find_one({"_id": OId(item_id)})
                    if item:
                        enriquecido.append({
                            "id":          str(item["_id"]),
                            "codigo":      item.get("codigo", ""),
                            "nombre":      item.get("nombre", item.get("descripcion", "")),
                            "descripcion": item.get("descripcion", ""),
                        })
                except Exception:
                    pass
            doc["ciiu_enriquecido"] = enriquecido

        # Enriquecer plan_contratado si existe
        if doc.get("info_contractual") and doc["info_contractual"].get("plan_contratado"):
            plan_str = doc["info_contractual"]["plan_contratado"]
            try:
                plan = PlanModel.buscar_por_slug(plan_str) or db["planes_saas"].find_one({"nombre": plan_str})
                if plan:
                    doc["plan_contratado_enriquecido"] = {
                        "id":          str(plan.get("_id", "")),
                        "nombre":      plan.get("nombre", ""),
                        "plan_id":     plan.get("plan_id", ""),
                        "descripcion": plan.get("descripcion", ""),
                    }
            except Exception:
                pass

        # Enriquecer tributos_aplicables dentro de info_tributaria
        it = doc.get("info_tributaria", {})
        if isinstance(it, dict) and isinstance(it.get("tributos_aplicables"), list):
            col_trib = db["tributos"]
            enriquecidos = []
            for item in it["tributos_aplicables"]:
                try:
                    tid = item.get("tributo_id", "") if isinstance(item, dict) else str(item)
                    found = col_trib.find_one({"_id": OId(tid)})
                    entry = {
                        "tributo_id":    tid,
                        "nombre":        found.get("nombre", "") if found else "",
                        "codigo":        found.get("codigo", "") if found else "",
                        "base_imponible": item.get("base_imponible", 0) if isinstance(item, dict) else 0,
                    }
                    enriquecidos.append(entry)
                except Exception:
                    pass
            doc["info_tributaria"]["tributos_aplicables"] = enriquecidos

        # Enriquecer tipo_organizacion dentro de info_tributaria
        if isinstance(it, dict) and it.get("tipo_organizacion"):
            try:
                found = db["tipos_organizacion"].find_one({"_id": OId(it["tipo_organizacion"])})
                if found:
                    doc["info_tributaria"]["tipo_organizacion_nombre"] = found.get("nombre", "")
            except Exception:
                pass

        return doc

    @staticmethod
    def crear(empresa_id: str, datos: dict, creado_por: str):
        if not empresa_id:
            return False, "ID de empresa requerido"
        for clave in ["representante_legal", "representante_suplente", "ciiu"]:
            if isinstance(datos.get(clave), str):
                try:    datos[clave] = json.loads(datos[clave])
                except Exception: pass

        rep = datos.get("representante_legal", {})
        if not all([rep.get("nombre_completo"), rep.get("tipo_doc"), rep.get("num_doc")]):
            return False, "Datos del representante legal incompletos"
        sup = datos.get("representante_suplente", {})
        if not all([sup.get("nombre_completo"), sup.get("tipo_doc"), sup.get("num_doc")]):
            return False, "Datos del representante suplente incompletos"

        doc_id = DatosGeneralesPHModel.crear(empresa_id, datos, creado_por)
        return True, {"id": doc_id, "mensaje": "Datos generales registrados correctamente"}

    @staticmethod
    def actualizar(empresa_id: str, datos: dict):
        if not empresa_id:
            return False, "ID de empresa requerido"
        for clave in ["representante_legal", "representante_suplente", "ciiu"]:
            if isinstance(datos.get(clave), str):
                try:    datos[clave] = json.loads(datos[clave])
                except Exception: pass

        rep = datos.get("representante_legal", {})
        if rep and isinstance(rep, dict) and not all([rep.get("nombre_completo"), rep.get("tipo_doc"), rep.get("num_doc")]):
            return False, "Datos del representante legal incompletos"
        sup = datos.get("representante_suplente", {})
        if sup and isinstance(sup, dict) and not all([sup.get("nombre_completo"), sup.get("tipo_doc"), sup.get("num_doc")]):
            return False, "Datos del representante suplente incompletos"

        DatosGeneralesPHModel.actualizar(empresa_id, datos)
        return True, "Datos generales actualizados correctamente"

    @staticmethod
    def obtener(empresa_id: str):
        if not empresa_id: return False, "ID de empresa requerido"
        doc = DatosGeneralesPHModel.obtener(empresa_id)
        if not doc: return False, "No existen datos generales para esta empresa"
        return True, DatosGeneralesPHController._enriquecer(doc)

    @staticmethod
    def listar():
        from app import db
        from app.configuracion.catalogos.model import CatalogoModel
        import base64

        # Mapa estado_contrato_id → nombre
        estados = {e["id"]: e["nombre"] for e in CatalogoModel.estados_contrato() if e.get("id")}

        # Todas las empresas (sin imágenes pesadas excepto logo)
        empresas = list(db["empresas"].find(
            {},
            {"razon_social": 1, "activo": 1, "estado_contrato_id": 1,
             "observaciones": 1, "logo_data": 1, "logo_mimetype": 1}
        ).sort("razon_social", 1))

        # Mapa empresa_id → doc datos_ph
        configs = {str(c["empresa_id"]): c for c in DatosGeneralesPHModel.listar()}

        resultado = []
        for emp in empresas:
            eid  = str(emp["_id"])
            cfg  = configs.get(eid, {})
            ec_id = str(emp.get("estado_contrato_id") or "")
            logo = None
            if emp.get("logo_data"):
                logo = f"data:{emp.get('logo_mimetype','image/png')};base64,{emp['logo_data']}"

            row = {
                "_id":                  cfg.get("_id") or None,
                "empresa_id":           eid,
                "empresa_nombre":       emp.get("razon_social", "—"),
                "empresa_logo":         logo,
                "empresa_estado":       estados.get(ec_id, "Activo" if emp.get("activo") else "Inactivo"),
                "empresa_descripcion":  emp.get("observaciones", "") or "",
                "estrato":              cfg.get("estrato", ""),
                "representante_legal":  cfg.get("representante_legal", {}),
                "info_contractual":     cfg.get("info_contractual", {}),
                "estado_configuracion": cfg.get("estado_configuracion", False),
                "creado_en":            cfg.get("creado_en"),
            }
            resultado.append(row)

        return True, resultado

    @staticmethod
    def eliminar(config_id: str):
        if not config_id: return False, "ID requerido"
        DatosGeneralesPHModel.eliminar(config_id)
        return True, "Configuración eliminada"
