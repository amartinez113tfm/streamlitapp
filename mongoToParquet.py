import pandas as pd
from pymongo import MongoClient
import datetime
import toml # Asegúrate de tenerlo: pip install toml
import os

# 1. Cargar la URI desde los secretos de Streamlit
def get_mongo_uri():
    # Buscamos en la carpeta estándar de Streamlit
    secrets_path = ".streamlit/secrets.toml"
    if not os.path.exists(secrets_path):
        raise FileNotFoundError(f"No se encuentra el archivo en {secrets_path}")
    
    # IMPORTANTE: Abrir en modo 'r' (texto), no 'rb'
    with open(secrets_path, "r", encoding="utf-8") as f:
        config = toml.load(f)
        # Ajusta 'MONGO_URI' al nombre exacto que pusiste en tu archivo
        return config["mongo"]["uri"] if "mongo" in config else config["MONGO_URI"]

def rescue_to_parquet():
    try:
        uri = get_mongo_uri()
        client = MongoClient(uri)
        db = client["trafico_madrid"] # Ajusta si tu DB se llama distinto
        coll = db["historico_trafico"]
        
        años = [2019,2020,2021,2022,2023, 2024, 2025,2026] 
        
        for anio in años:
            print(f"⏳ Procesando año {anio}...")
            start = datetime.datetime(anio, 1, 1)
            end = datetime.datetime(anio, 12, 31, 23, 59, 59)
            
            # Consultamos el año
            cursor = coll.find(
                {"timestamp": {"$gte": start, "$lte": end}},
                {"_id": 0}
            )
            
            df = pd.DataFrame(list(cursor))
            
            if not df.empty:
                # Guardar como Parquet
                output_name = f"trafico_madrid_{anio}.parquet"
                df.to_parquet(output_name, index=False, compression='snappy')
                print(f"✅ Exportado: {output_name} ({len(df)} filas)")
            else:
                print(f"❌ No se encontraron datos para {anio}")
                
        client.close()
        print("\n🚀 Migración finalizada con éxito.")

    except Exception as e:
        print(f"💥 Error durante la migración: {e}")

if __name__ == "__main__":
    rescue_to_parquet()