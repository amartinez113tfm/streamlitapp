# core/data_manager.py
import pandas as pd
import streamlit as st
from pymongo import MongoClient
from core import model_configs as mc
from datetime import datetime, time
from pandas import json_normalize


# Configuración de conexión (puedes mover la URI a un archivo .env o st.secrets)
MONGO_URI = st.secrets["MONGO_URI"]

@st.cache_resource
def get_db_connection():
    """Establece y cachea la conexión a MongoDB."""
    client = MongoClient(MONGO_URI)
    return client['madrid_aire']

def get_db_connectionTrafico():
    """Establece y cachea la conexión a MongoDB."""
    client = MongoClient(MONGO_URI)
    return client['trafico_madrid']


def get_traffic_data(estacion_id, fecha_inicio, fecha_fin):
    db = get_db_connectionTrafico()
    dt_inicio = datetime.combine(fecha_inicio, datetime.min.time())
    dt_fin = datetime.combine(fecha_fin, datetime.max.time())
    
    # Fecha del cambio de esquema
    FECHA_CORTE = datetime(2025, 12, 31)
    
    df_lista = []

    # 1. Consulta para datos antiguos (< 2025-04-20)
    if dt_inicio < FECHA_CORTE:
        query_old = {
            "estacion": estacion_id,
            "timestamp": {"$gte": dt_inicio, "$lt": min(dt_fin, FECHA_CORTE)}
        }
        data_old = list(db['trafico_historico'].find(query_old, {"_id": 0}))
        if data_old:
            df_old = pd.DataFrame(data_old)
            # --- NORMALIZACIÓN ESQUEMA ANTIGUO ---
            # Supongamos que antes se llamaba 'intensidad_vehicular'
            if 'valor' in df_old.columns:
                df_old = df_old.rename(columns={'valor': 'intensidad'})
            df_lista.append(df_old)

    # 2. Consulta para datos nuevos (>= 2025-04-20)
    if dt_fin >= FECHA_CORTE:
        query_new = {
            "estacion": str(estacion_id),
            "timestamp": {"$gte": max(dt_inicio, FECHA_CORTE), "$lte": dt_fin}
        }
        data_new = list(db['predicciones_horarias'].find(query_new, {"_id": 0}))
        if data_new:
            df_new = pd.DataFrame(data_new)
            # --- NORMALIZACIÓN ESQUEMA NUEVO ---
            # Supongamos que ahora los datos vienen anidados o con otro nombre
            # Ej: si vienen en 'metrics.flow', los aplanamos o renombramos
            if 'valor' in df_new.columns:
                df_new = df_new.rename(columns={'valor': 'intensidad'})
            df_lista.append(df_new)

    if not df_lista:
        return pd.DataFrame()

    # Unir ambos periodos
    df_trafico = pd.concat(df_lista, ignore_index=True)
    df_trafico['timestamp'] = pd.to_datetime(df_trafico['timestamp'])
    
    return df_trafico.sort_values("timestamp")



def get_all_station_traffic_data(fecha_inicio, fecha_fin):
    """
    Trae datos de MongoDB trafico de todas las estaciones.
    """
    db = get_db_connectionTrafico()
    dt_inicio = datetime.combine(fecha_inicio, datetime.min.time())
    dt_fin = datetime.combine(fecha_fin, datetime.max.time())
    
    # Fecha del cambio de esquema
    FECHA_CORTE = datetime(2025, 12, 31)
    
    df_lista = []

    # 1. Consulta para datos antiguos (< 2025-04-20)
    if dt_inicio < FECHA_CORTE:
        query_old = {
            
            "timestamp": {"$gte": dt_inicio, "$lt": min(dt_fin, FECHA_CORTE)}
        }
        data_old = list(db['trafico_historico'].find(query_old, {"_id": 0}))
        if data_old:
            df_old = pd.DataFrame(data_old)
            # --- NORMALIZACIÓN ESQUEMA ANTIGUO ---
            # Supongamos que antes se llamaba 'intensidad_vehicular'
            if 'valor' in df_old.columns:
                df_old = df_old.rename(columns={'valor': 'intensidad'})
            df_lista.append(df_old)

    # 2. Consulta para datos nuevos (>= 2025-04-20)
    if dt_fin >= FECHA_CORTE:
        query_new = {
            
            "timestamp": {"$gte": max(dt_inicio, FECHA_CORTE), "$lte": dt_fin}
        }
        data_new = list(db['predicciones_horarias'].find(query_new, {"_id": 0}))
        if data_new:
            df_new = pd.DataFrame(data_new)
            # --- NORMALIZACIÓN ESQUEMA NUEVO ---
            # Supongamos que ahora los datos vienen anidados o con otro nombre
            # Ej: si vienen en 'metrics.flow', los aplanamos o renombramos
            if 'valor' in df_new.columns:
                df_new = df_new.rename(columns={'valor': 'intensidad'})
            df_lista.append(df_new)

    if not df_lista:
        return pd.DataFrame()

    # Unir ambos periodos
    df_trafico = pd.concat(df_lista, ignore_index=True)
    df_trafico['timestamp'] = pd.to_datetime(df_trafico['timestamp'])
    
    return df_trafico.sort_values("timestamp")





def get_historical_data(estacion_id, contaminante, fecha_inicio,fecha_fin):
    """
    Trae datos de MongoDB filtrados por estación y contaminante.
    """
    db = get_db_connection()
    coleccion = db['historico_contaminantes']
    
    # El campo en el JSON es en minúsculas (o3, no2...)
    field_name = contaminante.lower()
    
    # Convertir date de Streamlit a datetime de Python para MongoDB
    # Ajustamos para que empiece a las 00:00 del primer día y termine a las 23:59 del último
    dt_inicio = datetime.combine(fecha_inicio, time.min)
    dt_fin = datetime.combine(fecha_fin, time.max)
    # Consulta: Filtrar por ID de estación y asegurar que el contaminante existe
    query = {
        "estacion_id": str(estacion_id), # En tu JSON viene como string "11"
        field_name: {"$exists": True},
        "timestamp": {
            "$gte": dt_inicio,
            "$lte": dt_fin
        }
    }
    
    # Traer solo los campos necesarios (Proyección)
    projection = {
        "timestamp": 1,
        field_name: 1,
        "_id": 0
    }
    
    # Ejecutar consulta y convertir a lista
    cursor = coleccion.find(query, projection).sort("timestamp", -1)
    data = list(cursor)
    
    if not data:
        return pd.DataFrame()

    # Crear DataFrame
    df = pd.DataFrame(data)
    
    # Normalizar el campo timestamp si viene como objeto de Mongo
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Renombrar para que la UI sea consistente
    df = df.rename(columns={field_name: f"valor_{contaminante}"})
    
    return df.sort_values("timestamp")




def get_combined_data(estacion_id, contaminante, fecha_inicio, fecha_fin):
    db = get_db_connection()
    dt_inicio = datetime.combine(fecha_inicio, time.min)
    dt_fin = datetime.combine(fecha_fin, time.max)
    
    field_name = contaminante.lower()

    # Consulta: Filtrar por ID de estación y asegurar que el contaminante existe
    query = {
        "estacion_id": str(estacion_id), # En tu JSON viene como string "11"
        field_name: {"$exists": True},
        "timestamp": {
            "$gte": dt_inicio,
            "$lte": dt_fin
        }
    }
    
    queryMeteo = {
        "estacion_id": str(estacion_id), 
        "timestamp": {
            "$gte": dt_inicio,
            "$lte": dt_fin
        }
    }

    # 1. Cargar Contaminantes
    df_cont = pd.DataFrame(list(db['historico_contaminantes'].find(query, {"_id": 0})))
    
    # 2. Cargar Meteorología
    cursor_meteo = db['meteorologia'].find(queryMeteo, {"_id": 0})
    list_meteo = list(cursor_meteo)
    
    # Debug: Si quieres ver en consola si alguna falla
    print(f"Contaminantes encontrados: {len(df_cont)}")
    print(f"Meteorología encontrada: {len(list_meteo)}")

    if not list_meteo or df_cont.empty:
        # Renombrar para que la UI sea consistente
        #df = df.rename(columns={field_name: f"valor_{contaminante}"})
        return pd.DataFrame()

    # IMPORTANTE: Aplanamos el diccionario 'variables'
    # Esto convertirá {"variables": {"temperatura": 10}} en la columna "variables.temperatura"
    df_meteo = json_normalize(list_meteo)
    
    # 3. Unir (Merge)
    # Nota: Asegúrate de que el timestamp en ambos sea datetime64[ns]
    df_cont['timestamp'] = pd.to_datetime(df_cont['timestamp'])
    df_meteo['timestamp'] = pd.to_datetime(df_meteo['timestamp'])
    
    df_final = pd.merge(df_cont, df_meteo, on=["timestamp", "estacion_id"], how="inner")
    # --- LIMPIEZA DE COLUMNAS PARA ALTAIR ---
    # Reemplazamos los puntos por guiones bajos para evitar problemas de parsing
    df_final.columns = [c.replace('.', '_') for c in df_final.columns]
    return df_final


def get_all_data_Trafico(fecha_inicio, fecha_fin):
    db = get_db_connection()
    dt_inicio = datetime.combine(fecha_inicio, time.min)
    dt_fin = datetime.combine(fecha_fin, time.max)
    
    

    # Consulta: todos los datos entre las fechas
    query = {
        "timestamp": {
            "$gte": dt_inicio,
            "$lte": dt_fin
        }
    }
    
    queryMeteo = {
        "timestamp": {
            "$gte": dt_inicio,
            "$lte": dt_fin
        }
    }

    # 1. Cargar Contaminantes
    df_cont = pd.DataFrame(list(db['historico_contaminantes'].find(query, {"_id": 0})))
    
    # 2. Cargar Meteorología
    cursor_meteo = db['meteorologia'].find(queryMeteo, {"_id": 0})
    list_meteo = list(cursor_meteo)
    
    # 3. Cargar Trafico
    df_trafico = get_all_station_traffic_data(fecha_inicio,fecha_fin)

    # Debug: Si quieres ver en consola si alguna falla
    print(f"Contaminantes encontrados: {len(df_cont)}")
    print(f"Meteorología encontrada: {len(list_meteo)}")
    print(f"Trafico encontrado: {len(df_trafico)}")

    if not list_meteo or df_cont.empty or df_trafico.empty:
        # Renombrar para que la UI sea consistente
        #df = df.rename(columns={field_name: f"valor_{contaminante}"})
        return pd.DataFrame()

    # IMPORTANTE: Aplanamos el diccionario 'variables'
    # Esto convertirá {"variables": {"temperatura": 10}} en la columna "variables.temperatura"
    df_meteo = json_normalize(list_meteo)
    
    # 3. Unir (Merge)
    # Nota: Asegúrate de que el timestamp en ambos sea datetime64[ns]
    df_cont['timestamp'] = pd.to_datetime(df_cont['timestamp'])
    df_meteo['timestamp'] = pd.to_datetime(df_meteo['timestamp'])
    df_trafico['timestamp'] = pd.to_datetime(df_meteo['timestamp'])
    df_trafico.rename(columns={'estacion':'estacion_id'})

    df_final = pd.merge(df_cont, df_meteo,df_trafico, on=["timestamp", "estacion_id"], how="inner")
    # --- LIMPIEZA DE COLUMNAS PARA ALTAIR ---
    # Reemplazamos los puntos por guiones bajos para evitar problemas de parsing
    df_final.columns = [c.replace('.', '_') for c in df_final.columns]
    return df_final