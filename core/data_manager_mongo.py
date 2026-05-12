# core/data_manager.py
import pandas as pd
import streamlit as st
from pymongo import MongoClient
from core import model_configs as mc
from datetime import datetime, time
from pandas import json_normalize


# Configuración de conexión (puedes mover la URI a un archivo .env o st.secrets)
# --- 1. GESTIÓN DE CONEXIÓN UNIFICADA (SINGLETON) ---

@st.cache_resource
def get_mongodb_client():
    """Crea un único cliente para toda la aplicación con timeouts de seguridad."""
    MONGO_URI = st.secrets["MONGO_URI"]
    # Añadimos parámetros para evitar el DNS Timeout
    return MongoClient(
        MONGO_URI,
        connectTimeoutMS=30000,
        serverSelectionTimeoutMS=30000,
        connect=False  # No conecta hasta la primera consulta real
    )

def get_db_connection(db_name='madrid_aire'):
    """Retorna la base de datos solicitada usando el cliente único."""
    client = get_mongodb_client()
    return client[db_name]

# Reemplazamos tu antigua función por un alias para no romper el resto del código
def get_db_connectionTrafico():
    return get_db_connection('trafico_madrid')


# --- 2. FUNCIONES DE TRÁFICO ---

def get_all_station_traffic_data(fecha_inicio, fecha_fin):
    db = get_db_connectionTrafico()
    dt_inicio = datetime.combine(fecha_inicio, datetime.min.time())
    dt_fin = datetime.combine(fecha_fin, datetime.max.time())
    
    query = {
        "timestamp": {"$gte": dt_inicio, "$lte": dt_fin}
    }
    
    # Traemos todo de la nueva colección única
    data = list(db['trafico_unificado'].find(query, {"_id": 0}))
    
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['estacion_id'] = df['estacion_id'].astype(str)
    
    return df.sort_values("timestamp")

# --- 3. FUNCIÓN DE DATOS TOTALES (MULTIESTACIÓN) ---

def get_all_data_Trafico(fecha_inicio, fecha_fin):
    db = get_db_connection('madrid_aire')
    dt_inicio = datetime.combine(fecha_inicio, time.min)
    dt_fin = datetime.combine(fecha_fin, time.max)
    
    query = {"timestamp": {"$gte": dt_inicio, "$lte": dt_fin}}

    # 1. Cargar Contaminantes
    df_cont = pd.DataFrame(list(db['historico_contaminantes'].find(query, {"_id": 0})))
    
    # 2. Cargar Meteorología
    list_meteo = list(db['meteorologia'].find(query, {"_id": 0}))
    
    # 3. Cargar Tráfico (desde la otra base de datos pero usando el mismo cliente)
    df_trafico = get_all_station_traffic_data(fecha_inicio, fecha_fin)

    if not list_meteo or df_cont.empty or df_trafico.empty:
        return pd.DataFrame()

    # Normalizar meteorología
    df_meteo = json_normalize(list_meteo)
    
    # Estandarizar tipos para el Merge
    for df in [df_cont, df_meteo, df_trafico]:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['estacion_id'] = df['estacion_id'].astype(str)

    # 4. UNIR (Merge encadenado)
    # Primero unimos Aire + Meteo
    df_final = pd.merge(df_cont, df_meteo, on=["timestamp", "estacion_id"], how="inner")
    # Luego unimos con Tráfico
    df_final = pd.merge(df_final, df_trafico, on=["timestamp", "estacion_id"], how="inner")

    # Limpiar nombres de columnas para Altair
    df_final.columns = [c.replace('.', '_') for c in df_final.columns]
    
    return df_final


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
    db_aire = get_db_connection('madrid_aire')
    db_trafico = get_db_connection('trafico_madrid')
    
    # Forzamos que las fechas no tengan microsegundos ni componentes extraños
    dt_inicio = datetime.combine(fecha_inicio, time.min).replace(microsecond=0)
    dt_fin = datetime.combine(fecha_fin, time.max).replace(microsecond=0)
    
    pollutant_field = contaminante.lower()
    estacion_str = str(estacion_id)

    query_base = {
        "estacion_id": estacion_str,
        "timestamp": {"$gte": dt_inicio, "$lte": dt_fin}
    }

    # 1. Aire y Meteo
    df_cont = pd.DataFrame(list(db_aire['historico_contaminantes'].find(query_base, {"_id": 0})))
    list_meteo = list(db_aire['meteorologia'].find(query_base, {"_id": 0}))
    
    # 2. Tráfico - Probamos una consulta más flexible si la exacta falla
    list_trafico = list(db_trafico['trafico_unificado'].find(query_base, {"_id": 0}))

    # DEBUG CRÍTICO: Si sigue dando 0, imprimimos la query para ver qué busca Python
    if len(list_trafico) == 0:
        print(f"DEBUG: Query Tráfico fallida: {query_base}")
        # Intento de rescate: ¿Hay algún dato de tráfico para esa estación aunque sea en otra fecha?
        ejemplo = db_trafico['trafico_unificado'].find_one({"estacion_id": estacion_str})
        if ejemplo:
            print(f"DEBUG: Encontrado dato de esta estación pero en fecha: {ejemplo['timestamp']}")
        else:
            print(f"DEBUG: No existen datos para la estación {estacion_str} en trafico_unificado")

    # 3. Procesamiento
    if df_cont.empty or not list_meteo:
        return pd.DataFrame()

    df_meteo = json_normalize(list_meteo)
    df_trafico = pd.DataFrame(list_trafico) if list_trafico else pd.DataFrame(columns=['timestamp', 'estacion_id', 'intensidad'])

    # 4. Sincronización de Timestamps (Crucial para el Merge)
    # Redondeamos a minutos para eliminar diferencias de milisegundos entre colecciones
    for temp_df in [df_cont, df_meteo, df_trafico]:
        if not temp_df.empty:
            temp_df['timestamp'] = pd.to_datetime(temp_df['timestamp']).dt.tz_localize(None).dt.round('min')
            temp_df['estacion_id'] = temp_df['estacion_id'].astype(str)

    # 5. Merges
    df_final = pd.merge(df_cont, df_meteo, on=["timestamp", "estacion_id"], how="inner")
    df_final = pd.merge(df_final, df_trafico, on=["timestamp", "estacion_id"], how="left")

    # Limpieza de columnas
    df_final.columns = [c.replace('.', '_') for c in df_final.columns]
    if 'intensidad' in df_final.columns:
        df_final['intensidad'] = df_final['intensidad'].fillna(0)
    
    return df_final.sort_values("timestamp")



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
    print(df_trafico.head(2))
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
    df_trafico['timestamp'] = pd.to_datetime(df_meteo['timestamp'])
    df_trafico.rename(columns={'estacion':'estacion_id'})

    df_trafico.head(1)

    # Primero unimos los dos primeros (Contaminantes + Meteorología)
    df_parcial = pd.merge(df_cont, df_meteo, on=["timestamp", "estacion_id"], how="inner")
    print(f'DF_PARCIAL tiene {len(df_parcial)}')
    df_parcial.head()
    # Luego el resultado lo unimos con el tercero (Tráfico)
    df_final = pd.merge(df_parcial, df_trafico, on=["timestamp", "estacion_id"], how="inner")

    
    # --- LIMPIEZA DE COLUMNAS PARA ALTAIR ---
    # Reemplazamos los puntos por guiones bajos para evitar problemas de parsing
    df_final.columns = [c.replace('.', '_') for c in df_final.columns]
    print(f'DF_FINAL tiene {len(df_final)}')
    df_final.head()
    return df_final


#Función para el radar.
def get_radar_data(df, contaminante):
    col_cont = contaminante.lower()
    
    # Columnas que queremos (usamos exactamente tus nombres)
    features = {
        col_cont: contaminante.upper(),
        'intensidad': 'Tráfico',
        'variables_temperatura': 'Temperatura',
        'variables_viento_velocidad': 'Viento',
        'variables_humedad': 'Humedad'
    }

    # 1. Extraemos los 5 mejores y 5 peores
    top_5 = df.nlargest(5, col_cont)
    bottom_5 = df.nsmallest(5, col_cont)

    # 2. Creamos una lista para guardar los datos manualmente
    radar_rows = []

    for estado, grupo in [('Máxima Contaminación', top_5), ('Mínima Contaminación', bottom_5)]:
        # Calculamos la media de cada grupo para simplificar el radar
        for col_db, nombre_bonito in features.items():
            if col_db in df.columns:
                # Normalizamos el valor medio respecto al min/max de todo el DF
                val_medio = grupo[col_db].mean()
                v_min = df[col_db].min()
                v_max = df[col_db].max()
                
                norm_val = (val_medio - v_min) / (v_max - v_min) if (v_max - v_min) != 0 else 0
                
                radar_rows.append({
                    'Estado': estado,
                    'Parámetro': nombre_bonito,
                    'Valor_Normalizado': float(norm_val)
                })

    # 3. Construimos el DataFrame directamente de la lista
    df_radar = pd.DataFrame(radar_rows)
    
    # DEBUG: Para estar seguros, imprime esto en tu streamlit
    st.write("Nuevo DF Radar:", df_radar)
    
    return df_radar


def get_all_contaminants_monthly(query_filter=None):
    """
    Extrae la media mensual de todos los contaminantes para todas las estaciones.
    Ideal para gráficos de horizontes y tendencias de largo plazo.
    """
    # 1. Asegurar la conexión y validar el filtro
    db = get_db_connection()
    db_collection = db['historico_contaminantes']
    
    # --- SOLUCIÓN AL ERROR TYPEERROR ---
    # Si query_filter es None o no es un diccionario, forzamos {}
    if query_filter is None or not isinstance(query_filter, dict):
        query_filter = {}
    # -----------------------------------

    # 2. Ejecutar consulta a MongoDB
    projection = {
        "timestamp": 1, 
        "estacion_id": 1, 
        "no2": 1, "o3": 1, "pm2_5": 1, "pm10": 1,
        "_id": 0
    }
    
    # Ahora query_filter es garantizadamente un diccionario
    cursor = db_collection.find(query_filter, projection)
    df = pd.DataFrame(list(cursor))
    
    if df.empty:
        return df

    # 3. Asegurar formato de fecha
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 4. Agrupación mensual por estación
    df_monthly = df.set_index('timestamp').groupby([
        pd.Grouper(freq='ME'), 
        'estacion_id'
    ]).mean().reset_index()
    
    return df_monthly




def get_polulant_by_year(year):
    """
    Se conecta a MongoDB y extrae los registros de un año específico.
    """
    try:
        db = get_db_connection()
        collection = db['historico_contaminantes']

        # 1. Definir el rango de fechas para el año seleccionado
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)

        # 2. Query de MongoDB: Filtramos por el campo 'timestamp'
        # Nota: Asegúrate de que en tu BD el campo se llame 'timestamp' y sea tipo Date
        query = {
            "timestamp": {
                "$gte": start_date,
                "$lte": end_date
            }
        }

        # 3. Proyección: Traemos solo lo necesario para ahorrar ancho de banda
        projection = {
            "_id": 0, 
            "timestamp": 1, 
            "estacion_id": 1, 
            "no2": 1, 
            "o3": 1, 
            "pm2_5": 1, 
            "pm10": 1
        }

        # 4. Ejecutar consulta y convertir a DataFrame
        cursor = collection.find(query, projection)
        df = pd.DataFrame(list(cursor))

        if not df.empty:
            # Aseguramos que el timestamp sea objeto datetime de Pandas
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
        
        return df

    except Exception as e:
        st.error(f"Error al conectar con MongoDB: {e}")
        return pd.DataFrame()