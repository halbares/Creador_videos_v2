#!/usr/bin/env python3
"""
Script para crear el sistema de cola de videos en Make.com
Usando la API directa de Make.com
"""

import os
import requests
import json
from dotenv import load_dotenv

# Cargar credenciales
load_dotenv("/home/pablo/Proyectos/MCP-MAKE/.env")

API_KEY = os.getenv("MAKE_API_KEY")
API_URL = os.getenv("MAKE_API_URL", "https://us2.make.com/api/v2")
TEAM_ID = os.getenv("MAKE_TEAM_ID")

headers = {
    "Authorization": f"Token {API_KEY}",
    "Content-Type": "application/json"
}

print("=" * 60)
print("🚀 CREADOR DE SISTEMA DE COLA DE VIDEOS EN MAKE.COM")
print("=" * 60)
print(f"API URL: {API_URL}")
print(f"Team ID: {TEAM_ID}")
print()

# ============================================================================
# PASO 1: Crear Data Store para la cola de videos
# ============================================================================
print("📦 PASO 1: Creando Data Store 'VideoQueue'...")

# Primero verificar si ya existe
ds_response = requests.get(
    f"{API_URL}/data-stores",
    headers=headers,
    params={"teamId": TEAM_ID}
)

existing_ds = None
if ds_response.status_code == 200:
    data_stores = ds_response.json().get("dataStores", [])
    for ds in data_stores:
        if ds.get("name") == "VideoQueue":
            existing_ds = ds
            print(f"   ✓ Data Store ya existe (ID: {ds['id']})")
            break

if not existing_ds:
    # Crear nuevo Data Store
    ds_create = requests.post(
        f"{API_URL}/data-stores",
        headers=headers,
        json={
            "name": "VideoQueue",
            "teamId": int(TEAM_ID)
        }
    )
    
    if ds_create.status_code in [200, 201]:
        existing_ds = ds_create.json().get("dataStore", ds_create.json())
        print(f"   ✓ Data Store creado (ID: {existing_ds.get('id')})")
    else:
        print(f"   ✗ Error creando Data Store: {ds_create.status_code}")
        print(f"   Respuesta: {ds_create.text}")

# ============================================================================
# PASO 2: Definir estructura del Data Store
# ============================================================================
if existing_ds:
    print("\n📋 PASO 2: Definiendo estructura del Data Store...")
    
    ds_id = existing_ds.get("id")
    
    # Definir estructura de la cola
    structure = {
        "dataStructure": {
            "name": "VideoQueueItem",
            "spec": [
                {"name": "video_url", "type": "text", "label": "URL del Video"},
                {"name": "title", "type": "text", "label": "Título"},
                {"name": "description", "type": "text", "label": "Descripción"},
                {"name": "hashtags", "type": "text", "label": "Hashtags"},
                {"name": "added_at", "type": "text", "label": "Fecha Agregado"},
                {"name": "status", "type": "text", "label": "Estado"}
            ]
        }
    }
    
    # Intentar crear/actualizar estructura
    struct_response = requests.post(
        f"{API_URL}/data-structures",
        headers=headers,
        json={
            "name": "VideoQueueItem",
            "teamId": int(TEAM_ID),
            "spec": structure["dataStructure"]["spec"]
        }
    )
    
    if struct_response.status_code in [200, 201]:
        struct_data = struct_response.json()
        print(f"   ✓ Estructura definida")
    else:
        print(f"   ⚠ Estructura puede que ya exista: {struct_response.status_code}")

# ============================================================================
# PASO 3: Crear Escenario del Webhook (agregar a cola)
# ============================================================================
print("\n🔗 PASO 3: Creando escenario 'CreadorVideos_AddQueue'...")

# Verificar si ya existe
scenarios_response = requests.get(
    f"{API_URL}/scenarios",
    headers=headers,
    params={"teamId": TEAM_ID}
)

webhook_scenario = None
publish_scenario = None

if scenarios_response.status_code == 200:
    scenarios = scenarios_response.json().get("scenarios", [])
    for s in scenarios:
        if s.get("name") == "CreadorVideos_AddQueue":
            webhook_scenario = s
            print(f"   ✓ Escenario webhook ya existe (ID: {s['id']})")
        if s.get("name") == "CreadorVideos_Publish":
            publish_scenario = s
            print(f"   ✓ Escenario publish ya existe (ID: {s['id']})")

if not webhook_scenario:
    # Crear escenario webhook
    webhook_create = requests.post(
        f"{API_URL}/scenarios",
        headers=headers,
        params={"teamId": TEAM_ID, "confirmed": "true"},
        json={
            "name": "CreadorVideos_AddQueue",
            "description": "Recibe videos del Creador de Videos y los agrega a la cola",
            "teamId": int(TEAM_ID),
            "scheduling": {
                "type": "indefinitely"
            }
        }
    )
    
    if webhook_create.status_code in [200, 201]:
        webhook_scenario = webhook_create.json().get("scenario", webhook_create.json())
        print(f"   ✓ Escenario webhook creado (ID: {webhook_scenario.get('id')})")
    else:
        print(f"   ✗ Error: {webhook_create.status_code} - {webhook_create.text}")

# ============================================================================
# PASO 4: Crear Escenario Programado (publicar)
# ============================================================================
print("\n⏰ PASO 4: Creando escenario 'CreadorVideos_Publish'...")

if not publish_scenario:
    publish_create = requests.post(
        f"{API_URL}/scenarios",
        headers=headers,
        params={"teamId": TEAM_ID, "confirmed": "true"},
        json={
            "name": "CreadorVideos_Publish",
            "description": "Publica videos de la cola a Facebook y YouTube (13:00, 18:00, 20:00)",
            "teamId": int(TEAM_ID),
            "scheduling": {
                "type": "indefinitely",
                "interval": 60  # Se configura manualmente después
            }
        }
    )
    
    if publish_create.status_code in [200, 201]:
        publish_scenario = publish_create.json().get("scenario", publish_create.json())
        print(f"   ✓ Escenario publish creado (ID: {publish_scenario.get('id')})")
    else:
        print(f"   ✗ Error: {publish_create.status_code} - {publish_create.text}")

# ============================================================================
# RESUMEN
# ============================================================================
print("\n" + "=" * 60)
print("📊 RESUMEN")
print("=" * 60)

if existing_ds:
    print(f"✓ Data Store 'VideoQueue': ID {existing_ds.get('id')}")
else:
    print("✗ Data Store: No creado")

if webhook_scenario:
    print(f"✓ Escenario 'CreadorVideos_AddQueue': ID {webhook_scenario.get('id')}")
else:
    print("✗ Escenario Webhook: No creado")

if publish_scenario:
    print(f"✓ Escenario 'CreadorVideos_Publish': ID {publish_scenario.get('id')}")
else:
    print("✗ Escenario Publish: No creado")

print("\n" + "=" * 60)
print("🔧 PRÓXIMOS PASOS (en Make.com)")
print("=" * 60)
print("""
1. Abrir 'CreadorVideos_AddQueue' y agregar:
   - Módulo Webhook (Custom webhook)
   - Módulo Data Store > Add record (a VideoQueue)
   
2. Abrir 'CreadorVideos_Publish' y agregar:
   - Trigger: Schedule (13:00, 18:00, 20:00)
   - Data Store > Search records (status = pending, limit 1)
   - Router con 2 ramas:
     - Facebook Pages > Create Video Post
     - YouTube > Upload Video
   - Data Store > Delete record

3. Activar ambos escenarios
""")

# Guardar IDs para referencia
config = {
    "data_store_id": existing_ds.get("id") if existing_ds else None,
    "webhook_scenario_id": webhook_scenario.get("id") if webhook_scenario else None,
    "publish_scenario_id": publish_scenario.get("id") if publish_scenario else None
}

with open("/home/pablo/Proyectos/Creador_videos_v2/make_queue_config.json", "w") as f:
    json.dump(config, f, indent=2)
    print(f"\n✓ Configuración guardada en make_queue_config.json")
