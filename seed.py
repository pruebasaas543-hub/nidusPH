"""
Inicializa / repara los usuarios SuperAdmin en MongoDB.
Comando: python seed.py

Comportamiento:
  - Para cada usuario listado en ADMINS:
      Si ya existe en BD → garantiza rol="SuperAdmin" y activo=True.
      Si no existe       → lo crea.
"""

from app import create_app

app = create_app()

# Lista de usuarios que SIEMPRE deben tener rol SuperAdmin.
# Agregar aqui nuevos admins si se necesitan.
ADMINS = [
    {
        "tipo_doc": "CC",
        "num_doc":  "1116613889",
        "password": "1116613889",          # se cambia en primer login
        "email":    "andres.plazas@est.iudigital.edu.co",
        "telefono": "3213895559",
        "nombres":  "ANDRES",
        "apellidos":"PLAZAS",
    },
]

with app.app_context():
    from app.auth.model import UserModel
    from app import db
    from datetime import datetime

    print("=== Inicializacion de SuperAdmins ===")

    for admin in ADMINS:
        tipo = admin["tipo_doc"]
        num  = admin["num_doc"]

        existente = db["users"].find_one({
            "tipo_documento":   tipo,
            "numero_documento": num,
        })

        if existente:
            rol_actual = existente.get("rol")
            db["users"].update_one(
                {"tipo_documento": tipo, "numero_documento": num},
                {"$set": {
                    "rol":                  "SuperAdmin",
                    "activo":               True,
                    "intentos_fallidos":    0,
                    "bloqueado_hasta":      None,
                    "ultima_actualizacion": datetime.utcnow(),
                }}
            )
            print(f"[OK] {tipo} {num} -> rol actualizado a SuperAdmin (era: {rol_actual!r})")
        else:
            uid = UserModel.crear_usuario(
                tipo_doc  = tipo,
                num_doc   = num,
                password  = admin["password"],
                rol       = "SuperAdmin",
                email     = admin.get("email", ""),
                telefono  = admin.get("telefono", ""),
                nombres   = admin.get("nombres", ""),
                apellidos = admin.get("apellidos", ""),
            )
            print(f"[OK] {tipo} {num} -> SuperAdmin creado (ID: {uid})")

    print("=== Listo ===")
