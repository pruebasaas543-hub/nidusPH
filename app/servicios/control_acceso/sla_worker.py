"""
app/servicios/control_acceso/sla_worker.py
───────────────────────────────────────────
Hilo daemon que revisa cada 30 minutos las credenciales de contratistas
pendientes de aprobación. Si han pasado `alerta_porcentaje`% del SLA,
envía un WhatsApp a los admins del conjunto para que actúen.

Solo corre una instancia (bandera `_iniciado`).
"""

import threading
import time
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

_iniciado = False
_INTERVALO_SEG = 30 * 60  # 30 minutos


def _verificar_slas():
    """Recorre todos los conjuntos con contratistas pendientes y alerta si procede."""
    try:
        from app import db
        from app.servicios.control_acceso.config_model import CaConfigModel
        from app.servicios.control_acceso.controller import AccessController

        # Todas las credenciales pendientes de aprobación, agrupadas por conjunto
        pendientes = list(db["access_credentials"].find(
            {"estado": "pendiente_aprobacion"},
            {"conjunto_id": 1, "creado_en": 1, "aprobacion": 1, "visitante": 1, "solicitante_id": 1}
        ))

        conjuntos_vistos = set()
        for cred in pendientes:
            cid = str(cred.get("conjunto_id", ""))
            if not cid:
                continue

            # No cargar la config mil veces para el mismo conjunto
            if cid not in conjuntos_vistos:
                conjuntos_vistos.add(cid)

            cfg = CaConfigModel.obtener(cid)
            flujo = cfg.get("flujo_contratistas", {})
            sla_horas = flujo.get("sla_horas", 24)
            alerta_pct = flujo.get("alerta_porcentaje", 75)

            creado_en = cred.get("creado_en")
            if not creado_en:
                continue

            ya_alertado = cred.get("aprobacion", {}).get("alerta_enviada", False)
            if ya_alertado:
                continue

            ahora = datetime.utcnow()
            tiempo_transcurrido = (ahora - creado_en).total_seconds() / 3600  # en horas
            umbral_horas = sla_horas * (alerta_pct / 100.0)

            if tiempo_transcurrido >= umbral_horas:
                # Marcar alerta enviada antes de notificar (evitar duplicados)
                db["access_credentials"].update_one(
                    {"_id": cred["_id"]},
                    {"$set": {"aprobacion.alerta_enviada": True}}
                )
                try:
                    AccessController.notificar_admin_nuevo_contratista(cred, cid)
                    log.info("SLA alerta enviada: cred=%s conjunto=%s (%.1fh de %dh SLA)",
                             str(cred["_id"]), cid, tiempo_transcurrido, sla_horas)
                except Exception as e:
                    log.warning("SLA alerta error: %s", e)
    except Exception as e:
        log.warning("SLA worker error: %s", e)


def _loop():
    while True:
        time.sleep(_INTERVALO_SEG)
        _verificar_slas()


def iniciar_sla_worker():
    global _iniciado
    if _iniciado:
        return
    _iniciado = True
    t = threading.Thread(target=_loop, name="sla-contratistas", daemon=True)
    t.start()
    log.info("SLA worker iniciado (intervalo=%ds)", _INTERVALO_SEG)
