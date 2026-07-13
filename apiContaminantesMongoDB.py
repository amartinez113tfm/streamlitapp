from datetime import datetime
import pymongo
import requests
import streamlit as st

# 1. Configuración de conexiones
MONGO_URI = st.secrets["MONGO_URI"]  # Cambia por tu URI de producción o Atlas
client = pymongo.MongoClient(MONGO_URI)
db = client["madrid_aire"]  # Cambia por el nombre de tu BD
coleccion_contaminantes = db["contaminacion"]

# Creacion del indice unico compuesto para evitar duplicados al descargar 30 dias
coleccion_contaminantes.create_index(
    [
        ("estacion_id", pymongo.ASCENDING),
        ("timestamp", pymongo.ASCENDING),
        ("contaminante", pymongo.ASCENDING),
    ],
    unique=True,
)

# URL oficial del JSON de datos en tiempo real del Ayuntamiento de Madrid
API_URL = "https://ciudadesabiertas.madrid.es/dynamicAPI/API/query/calair_tiemporeal_ult.json?pageSize=5000"

def descargar_y_guardar_contaminantes():
    print(f"[{datetime.now()}] Conectando con la API del Ayuntamiento...")

    try:
        response = requests.get(API_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error al conectar con la API: {e}")
        return

    # --- BLOQUE DE DEPURACION ---
    # Esto te imprimira en la terminal las claves principales del JSON para ver que responde
    print(f"Llaves encontradas en el JSON de la API: {list(data.keys())}")
    
    registros_api = data.get("records", [])
    print(f"Numero de registros encontrados en 'records': {len(registros_api)}")
    
    if len(registros_api) > 0:
        print(f"Ejemplo de las llaves del primer registro: {list(registros_api[0].keys())}")
    # -----------------------------

    documentos_a_insertar = []

    # Mapa de magnitudes (incluyendo el PM2.5 solicitado)
    mapa_magnitudes = {
        "1": "SO2",
        "6": "CO",
        "7": "NO",
        "8": "NO2",
        "9": "PM2_5",  
        "10": "PM10",
        "14": "O3",  
    }

    # Procesamiento de los registros
    for reg in registros_api:
        id_magnitud = str(reg.get("MAGNITUD"))
        
        if id_magnitud not in mapa_magnitudes:
            continue

        nombre_contaminante = mapa_magnitudes[id_magnitud]
        codigo_estacion = str(reg.get("ESTACION")).lstrip("0")
        
        try:
            año = int(reg.get("ANO"))
            mes = int(reg.get("MES"))
            dia = int(reg.get("DIA"))
        except (ValueError, TypeError):
            # Si las fechas no son validas o vienen nulas, saltamos el registro
            continue

        # Recorremos las 24 horas del dia
        for h in range(1, 25):
            clave_hora = f"H{h:02d}"
            clave_val = f"V{h:02d}"

            if clave_hora in reg and reg.get(clave_val) == "V":
                try:
                    valor_medido = float(reg[clave_hora])
                    hora_ajustada = h - 1
                    fecha_registro = datetime(año, mes, dia, hora_ajustada)

                    doc = {
                        "estacion_id": codigo_estacion,
                        "timestamp": fecha_registro,
                        "contaminante": nombre_contaminante,
                        "valor": valor_medido,
                        "actualizado_el": datetime.utcnow(),
                    }
                    documentos_a_insertar.append(doc)
                except (ValueError, TypeError):
                    continue

    # Insercion o actualizacion en MongoDB (Upsert)
    if documentos_a_insertar:
        operaciones = [
            pymongo.UpdateOne(
                {
                    "estacion_id": doc["estacion_id"],
                    "timestamp": doc["timestamp"],
                    "contaminante": doc["contaminante"],
                },
                {"$set": doc},
                upsert=True,
            )
            for doc in documentos_a_insertar
        ]

        resultado = coleccion_contaminantes.bulk_write(operaciones)
        print(f"Proceso completado. Registros nuevos/actualizados: {resultado.upserted_count + resultado.modified_count}")
    else:
        print("No se encontraron registros validos para insertar.")

if __name__ == "__main__":
    descargar_y_guardar_contaminantes()