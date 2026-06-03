#!/usr/bin/env python3
"""
Test para validar que los filtros del log funcionan correctamente
"""
from app import create_app
import app as app_module
from bson import ObjectId
from datetime import datetime, timezone

app = create_app()

with app.app_context():
    db = app_module.db
    if db is None:
        print("ERROR: Base de datos no inicializada")
        exit(1)

    empresa_id = ObjectId("69e7d5b72fb900aca7812c02")

    # Obtener todos los eventos
    todos = list(db["panic_events"].find({"empresa_id": empresa_id}).sort("activado_en", -1))

    print(f"\n{'='*60}")
    print(f"TOTAL EVENTOS: {len(todos)}")
    print(f"{'='*60}\n")

    # Test 1: Filtro por WhatsApp
    print("TEST 1: FILTRO POR WHATSAPP")
    print("-" * 60)

    canal_fil = "whatsapp"
    filtrados = []

    for ev in todos:
        res = ev.get("resultado", {})
        externos = res.get("externos", [])
        directorio = res.get("directorio", [])
        todos_contactos = externos + directorio

        evento_coincide = False
        for contacto in todos_contactos:
            canales = contacto.get("canales", {})
            for tipo_canal, info_canal in canales.items():
                # Verificar canal
                if tipo_canal.lower() == canal_fil.lower():
                    evento_coincide = True
                    break
            if evento_coincide:
                break

        if evento_coincide:
            filtrados.append(ev)
            print(f"[OK] INCLUIDO: {ev.get('nombre_residente')} - {tipo_canal}")
        else:
            print(f"[NO] EXCLUIDO: {ev.get('nombre_residente')}")

    print(f"\nEventos con WhatsApp: {len(filtrados)} de {len(todos)}")

    # Test 2: Filtro por SMS
    print("\n\nTEST 2: FILTRO POR SMS")
    print("-" * 60)

    canal_fil = "sms"
    filtrados = []

    for ev in todos:
        res = ev.get("resultado", {})
        externos = res.get("externos", [])
        directorio = res.get("directorio", [])
        todos_contactos = externos + directorio

        evento_coincide = False
        for contacto in todos_contactos:
            canales = contacto.get("canales", {})
            for tipo_canal, info_canal in canales.items():
                if tipo_canal.lower() == canal_fil.lower():
                    evento_coincide = True
                    break
            if evento_coincide:
                break

        if evento_coincide:
            filtrados.append(ev)
            print(f"[OK] INCLUIDO: {ev.get('nombre_residente')} - {tipo_canal}")
        else:
            print(f"[NO] EXCLUIDO: {ev.get('nombre_residente')}")

    print(f"\nEventos con SMS: {len(filtrados)} de {len(todos)}")

    # Test 3: Filtro por estado "delivered"
    print("\n\nTEST 3: FILTRO POR ESTADO 'delivered'")
    print("-" * 60)

    estado_fil = "delivered"
    filtrados = []

    for ev in todos:
        res = ev.get("resultado", {})
        externos = res.get("externos", [])
        directorio = res.get("directorio", [])
        todos_contactos = externos + directorio

        evento_coincide = False
        for contacto in todos_contactos:
            canales = contacto.get("canales", {})
            for tipo_canal, info_canal in canales.items():
                estado_actual = (info_canal.get("estado") or "").lower()
                if estado_actual == estado_fil.lower():
                    evento_coincide = True
                    print(f"  - {tipo_canal}: {estado_actual} OK")
                    break
            if evento_coincide:
                break

        if evento_coincide:
            filtrados.append(ev)
            print(f"OK INCLUIDO: {ev.get('nombre_residente')}")
        else:
            print(f"NO EXCLUIDO: {ev.get('nombre_residente')}")

    print(f"\nEventos con estado 'delivered': {len(filtrados)} de {len(todos)}")

    # Test 4: Mostrar estructura de un evento
    print("\n\nESTRUCTURA DE PRIMER EVENTO:")
    print("-" * 60)
    if todos:
        ev = todos[0]
        res = ev.get("resultado", {})
        print(f"Evento: {ev.get('nombre_residente')}")
        print(f"Externos: {len(res.get('externos', []))}")
        for c in res.get("externos", []):
            print(f"  - {c.get('nombre')}")
            for tipo, data in c.get("canales", {}).items():
                print(f"    * {tipo}: {data.get('estado')}")

print("\n" + "="*60)
print("TESTS COMPLETADOS")
print("="*60 + "\n")
