#!/usr/bin/env python3
"""
Script de migración: panic_configurations.contactos_externos → user_panic_contacts

Uso:
  python scripts/migrar_contactos_externos.py              # Migra todos (creado_por: sistema)
  python scripts/migrar_contactos_externos.py --usuario-id 1069749364  # Asignar a usuario
  python scripts/migrar_contactos_externos.py --empresa-id 60d5ec49b8e6f20015a3f8c1  # Solo una empresa
"""

import sys
import argparse
from datetime import datetime
from bson import ObjectId
import app as app_module

def migrar_contactos(usuario_id=None, empresa_id=None):
    """Migrar contactos_externos de panic_configurations a user_panic_contacts."""

    db = app_module.db
    if db is None:
        print("ERROR: Base de datos no inicializada")
        return False

    cfg_col = db["panic_configurations"]
    uc_col = db["user_panic_contacts"]

    # Obtener empresas a migrar
    if empresa_id:
        empresas = [cfg_col.find_one({"empresa_id": ObjectId(empresa_id)})]
        if not empresas[0]:
            print(f"❌ Empresa {empresa_id} no encontrada")
            return False
    else:
        empresas = list(cfg_col.find({"contactos_externos": {"$exists": True, "$ne": []}}))

    if not empresas:
        print("✅ No hay contactos para migrar")
        return True

    total_migrados = 0
    usuario_oid = ObjectId(usuario_id) if usuario_id else None
    ahora = datetime.utcnow()

    for cfg in empresas:
        eid = cfg.get("empresa_id")
        contactos = cfg.get("contactos_externos", [])

        if not contactos:
            continue

        print(f"\n[EMPRESA] {eid}")
        print(f"   Contactos a migrar: {len(contactos)}")

        migrados = 0
        para_insertar = []

        for contacto in contactos:
            # Evitar duplicados
            existe = uc_col.find_one({
                "empresa_id": eid,
                "nombre": contacto.get("nombre"),
                "telefono": f"{contacto.get('prefijo', '+57')}{contacto.get('celular', '')}",
            })

            if existe:
                print(f"   [SKIP] {contacto.get('nombre')} - ya existe")
                continue

            doc = {
                "usuario_id": usuario_oid,  # None para "sistema"
                "empresa_id": eid,
                "nombre": contacto.get("nombre", ""),
                "telefono": f"{contacto.get('prefijo', '+57')}{contacto.get('celular', '')}",
                "descripcion": "Migrado de configuración empresa",
                "habilitado": True,
                "creado_en": ahora,
                "actualizado_en": ahora,
            }
            para_insertar.append(doc)
            migrados += 1

        if para_insertar:
            result = uc_col.insert_many(para_insertar)
            print(f"   [OK] {len(result.inserted_ids)} insertados")
            total_migrados += len(result.inserted_ids)

            # Limpiar contactos_externos
            cfg_col.update_one(
                {"_id": cfg["_id"]},
                {"$unset": {"contactos_externos": ""}}
            )
            print(f"   [CLEAN] panic_configurations limpiado")

    print(f"\n{'='*60}")
    print(f"[OK] MIGRACIÓN COMPLETADA")
    print(f"   Total migrados: {total_migrados}")
    print(f"   Creado por: {'usuario ' + usuario_id if usuario_id else 'sistema'}")
    print(f"{'='*60}\n")

    return True

if __name__ == "__main__":
    app_obj = app_module.create_app()

    with app_obj.app_context():
        parser = argparse.ArgumentParser(description="Migrar contactos_externos a user_panic_contacts")
        parser.add_argument("--usuario-id", help="Asignar contactos a usuario específico (num_doc)")
        parser.add_argument("--empresa-id", help="Migrar solo una empresa (ObjectId)")
        args = parser.parse_args()

        try:
            exito = migrar_contactos(usuario_id=args.usuario_id, empresa_id=args.empresa_id)
            sys.exit(0 if exito else 1)
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
