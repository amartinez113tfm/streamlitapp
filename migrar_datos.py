import pandas as pd
#from core import data_manager as dm
from datetime import datetime
from pymongo import MongoClient
from core import util as ut



import toml  # En Python 3.11+
# O si usas una versión anterior: import toml

with open(".streamlit/secrets.toml", "rb") as f:
    config = toml.load(f)
    mongo_uri = config["MONGO_URI"] # O como la hayas nombrado
'''
def prueba():
    # check_schema.py
    db = dm.get_db_connectionTrafico()
    doc = db['trafico_historico'].find_one()
    print("--- COLECCIONES DISPONIBLES EN TRAFICO_MADRID ---")
    print(db.list_collection_names())
    print("--- ESQUEMA REAL DE TRAFICO_HISTORICO ---")
    print(doc)

def unificacion_final():
    db = dm.get_db_connectionTrafico()
    nueva_col = db['trafico_unificado']
    
    print("🧹 Vaciando 'trafico_unificado' para corregir el error de nombres...")
    nueva_col.delete_many({})

    # 1. MIGRAR DESDE 'historico_trafico' (EL NOMBRE CORRECTO)
    print("📦 Migrando desde 'historico_trafico'...")
    # Usamos el nombre exacto que te ha salido en la lista
    docs_hist = list(db['historico_trafico'].find())
    count_hist = 0
    
    for doc in docs_hist:
        # Extraemos la estación y la limpiamos (quitamos ceros y espacios)
        raw_estacion = str(doc.get('estacion', doc.get('estacion_id', '')))
        estacion_limpia = raw_estacion.strip().lstrip('0')
        
        if estacion_limpia and doc.get('timestamp'):
            nueva_col.insert_one({
                "estacion_id": estacion_limpia,
                "timestamp": doc['timestamp'],
                "intensidad": float(doc.get('valor', doc.get('intensidad', 0))),
                "tipo": "historico"
            })
            count_hist += 1
    
    print(f"✅ ¡Éxito! {count_hist} registros recuperados del pasado.")

    # 2. MIGRAR DESDE 'predicciones_horarias'
    print("🔮 Migrando desde 'predicciones_horarias'...")
    docs_pred = list(db['predicciones_horarias'].find())
    count_pred = 0
    for doc in docs_pred:
        raw_estacion = str(doc.get('estacion', doc.get('estacion_id', '')))
        estacion_limpia = raw_estacion.strip().lstrip('0')
        
        if estacion_limpia and doc.get('timestamp'):
            nueva_col.insert_one({
                "estacion_id": estacion_limpia,
                "timestamp": doc['timestamp'],
                "intensidad": float(doc.get('valor', doc.get('intensidad', 0))),
                "tipo": "prediccion"
            })
            count_pred += 1
            
    print(f"✅ {count_pred} registros migrados de predicciones.")
    
    # 3. ÍNDICES
    nueva_col.create_index([("estacion_id", 1), ("timestamp", 1)])
    print("⭐ Proceso terminado. Ya puedes volver a Streamlit.")

# Ejecuta esto una vez para crear tu "almacén" de datos rápido
def export_mongo_to_parquet(uri, db_name, coll_name):
    client = MongoClient(uri)
    db = client[db_name]
    df = pd.DataFrame(list(db[coll_name].find({}, {"_id": 0})))
    
    # Aseguramos tipos antes de guardar
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Guardar en formato Parquet
    df.to_parquet('contaminacion_historicos.parquet', compression='snappy')
    print("¡Archivo Parquet creado con éxito!")

import pandas as pd
from pymongo import MongoClient
'''
def migrate_to_parquet():
    with open(".streamlit/secrets.toml", "rb") as f:
        config = toml.load(f)
        mongo_uri = config["MONGO_URI"] # O como la hayas nombrado
    uri = mongo_uri
    client = MongoClient(uri)
    db = client["madrid_aire"]
    coll = db["historico_contaminantes"]
    
    # Lista de años que tienes en la base de datos
    años = [2019,2020,2021,2022,2023, 2024, 2025] 
    
    for anio in años:
        print(f"Extrayendo año {anio}...")
        import datetime
        start = datetime.datetime(anio, 1, 1)
        end = datetime.datetime(anio, 12, 31, 23, 59)
        
        # Extraemos solo un año y solo las columnas necesarias para ahorrar espacio
        cursor = coll.find(
            {"timestamp": {"$gte": start, "$lte": end}},
            {"_id": 0} 
        )
        
        df_anio = pd.DataFrame(list(cursor))
        
        if not df_anio.empty:
            # Guardamos un archivo por año (Mucho más manejable)
            file_name = f"contaminante_madrid_{anio}.parquet"
            df_anio.to_parquet(file_name, compression='snappy')
            print(f"✅ Guardado: {file_name} ({len(df_anio)} filas)")
        else:
            print(f"⚠️ No hay datos para {anio}")

    client.close()



if __name__ == "__main__":
   #unificacion_final()
   #prueba()
   
   
   #export_mongo_to_parquet(MONGO_URI,'madrid_aire','historico_contaminantes')
   migrate_to_parquet()